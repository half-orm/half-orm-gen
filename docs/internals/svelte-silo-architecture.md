# Svelte frontend — Silo architecture

## Overview

> General principles (silo pattern, route cache, WebSocket): [frontend-architecture.md](frontend-architecture.md)  
> Angular equivalent: [angular-silo-architecture.md](angular-silo-architecture.md)  
> Backend API: [litestar-architecture.md](litestar-architecture.md)  
> Access control (signals, buttons, FK auto-resolve): [svelte/access-control.md](../svelte/access-control.md)  
> Looking for the full `ResourceSilo` member list instead of internals? [frontend/resource-silo-reference.md](../frontend/resource-silo-reference.md)

The Svelte frontend uses a **silo-per-resource** pattern: one `ResourceSilo` instance per
database relation, all registered in a singleton `SiloRegistry`. There is no Svelte store
created per-relation in generated code; only the silo assets and the per-relation components
(List, Detail, Fields, Create) are generated.

---

## SiloRegistry

**File**: `src/lib/generated/stores/silo-registry.svelte.ts`

Singleton (module-level `const registry`). Initialised once on app boot by calling
`registry.init(apiBase)`, which:

1. Fetches `GET /ho_meta` (→ [litestar-architecture.md — Special endpoints](litestar-architecture.md#special-endpoints)) → receives a `HoMeta` JSON object (one entry per relation).
2. Creates one `ResourceSilo` per entry and stores it in an internal `Map<key, ResourceSilo>`.
3. Sets `_ready = true` — subsequent calls to `init()` are no-ops.

Key methods:

| Method | Description |
|---|---|
| `init(apiBase)` | Bootstrap (idempotent). |
| `get(key)` | Return the silo for `"schema/table"`, throws if missing. |
| `tryGet(key)` | Same but returns `undefined` instead of throwing. |
| `keys()` | All registered resource keys. |

---

## ResourceSilo

**File**: `src/lib/generated/stores/resource.silo.svelte.ts`

All fields marked `$state` are **Svelte 5 reactive runes** — reads inside `$derived` or
`$effect` are automatically tracked.

### Reactive state

| Field | Type | Description |
|---|---|---|
| `items` | `Row[]` | Ordered list for the current unfiltered view. |
| `byId` | `Map<string, Row>` | All fetched rows indexed by PK string. |
| `isLoading` | `boolean` | True while a fetch is in flight. |
| `hasMore` | `boolean` | Whether the API reported more pages. |
| `currentOffset` | `number` | Next offset for `loadMore`. |
| `filters` | `Record<string, string>` | Active local filter state (used by List for URL sync). |
| `selectedId` | `string \| null` | Highlighted row id. |
| `sortField / sortAsc` | `string \| null / boolean` | Current sort column and direction. |

### Private (non-reactive) state

| Field | Type | Description |
|---|---|---|
| `loadedFilters` | `Map<string, boolean>` | Tracks filter combinations whose full result set has been fetched (`has_more === false`). Keyed by `JSON.stringify(params)`. |

---

## Data flow: `silo.list(params, offset)`

```
list(params, offset=0)
  │
  ├─ [guard] loadedFilters.get(JSON.stringify(params)) && offset===0  → return (already complete)
  ├─ [guard] isLoading                                                 → return (in-flight)
  │
  ├─ Build URL:  baseUrl + ?ho_col_<field>=<value>&...&limit=100[&offset=N]
  │
  ├─ [guard] auth.fetchedRoutes.has(url)                              → return (deduplicated)
  ├─  auth.fetchedRoutes.add(url)
  │
  ├─ fetch(url)
  │
  ├─ if params==={} && offset===0   → _setItems(data)   (replaces items + byId)
  └─ else                           → _mergeItems(data)  (adds to byId, rebuilds items)
```

### `_setItems` vs `_mergeItems`

- **`_setItems`**: used for the plain unfiltered list. Replaces both `items` and `byId`.
- **`_mergeItems`**: used for filtered results, load-more, and all FK-filtered embedded lists.
  Adds new rows to `byId`, then rebuilds `items` from `byId.values()`. This means
  filtered results accumulate in the same silo alongside the unfiltered ones — a single silo
  holds all rows ever fetched for that resource regardless of the filter used.

---

## Request deduplication: `auth.fetchedRoutes`

**File**: `src/lib/auth.svelte.ts`

```typescript
fetchedRoutes = new Set<string>();   // plain Set, NOT $state
```

A plain (non-reactive) `Set` on the `AuthState` singleton. Before every fetch the silo checks
`fetchedRoutes.has(url)` and skips the request if true, then immediately adds the URL before
awaiting the response. This prevents redundant network calls when multiple components mount
concurrently and request the same resource.

**Lifecycle**:

- Cleared on `login()` and `logout()` (along with silo data via `clearAllStates()` which
  calls `silo.clear()` on every registered silo).
- **Not cleared on navigation** — it persists for the whole session.

`silo.clear()` flushes `items`, `byId`, and `loadedFilters` inside each `ResourceSilo`.
The `SiloRegistry` itself is **not** reset on login/logout: `_ready`, the silos Map, and
`meta` all survive. Only the data inside each silo is flushed.

Because `fetchedRoutes` is a plain `Set` (not `$state`), reading it inside a `$derived` or
`$effect` does **not** create a reactive dependency. This is intentional: the set is a
fire-and-forget dedup guard, not observable state.

---

## `displayItems` in List components

List components compute displayed rows client-side:

```typescript
const displayItems = $derived.by(() => {
  let items = hasFilters
    ? Array.from(silo.byId.values()).filter(item =>
        Object.entries(filters).every(([k, v]) => String(item[k]) === String(v)))
    : silo.items;
  // then apply localFilters and sort …
});
```

- **`hasFilters = true`** (embedded Related card with FK filter): scans `byId` in-memory.
  Data arrives when the `$effect(() => { void silo.list(filters); })` resolves and
  `_mergeItems` updates `byId`. The derived recomputes automatically.
- **`hasFilters = false`** (standalone List page): uses `silo.items` directly.

### Known limitation — empty Related cards on first load

Because `fetchedRoutes` is session-persistent, a filtered URL like
`/v0/public/foo?ho_col_bar=<id>&limit=100` is only fetched once. If the user navigates away
and back to the same detail page the silo already holds the data in `byId` (visible
immediately), but if it was never fetched at all the Related card will appear empty until the
`$effect` fires and the fetch completes. In practice the card fills in within one network
round-trip, but it may flash empty on slow connections.

A more subtle case: if the filtered fetch is skipped because `isLoading` is true at mount
time (another fetch was in flight for the same silo), the `$effect` will not retry. The card
stays empty until the next reactive trigger (e.g., auth token refresh). Mitigation: call
`silo.resetFilterState()` before navigating to a detail page, or remove the `isLoading`
guard for filtered calls.

---

## WebSocket live updates

> Backend reference: [litestar-architecture.md — WebSocket live updates](litestar-architecture.md#websocket-live-updates)

`AuthState._connectWs()` opens a WebSocket to `/v0/ws`. Each message sets
`auth.lastEvent = { event, resource, id }`. Every `ResourceSilo` registers a
`$effect.root` listener that:

- `delete` → `silo.removeItem(id)`
- `create` / `update` → `silo.refresh(id)` (GET single item)

The `$effect.root` is created in the constructor so it lives for the lifetime of the silo,
independent of any component tree.

---

## Lifecycle summary

```
App boot
  └─ registry.init()  →  fetch /ho_meta  →  create ResourceSilo × N
        └─ each silo registers $effect.root for WS events

Login / logout
  └─ auth.fetchedRoutes = new Set()
  └─ clearAllStates()  →  silo.clear() × N   (items=[], byId=new Map(), loadedFilters.clear())
       SiloRegistry NOT reset — _ready/silos Map/meta persist

Navigate to List page
  └─ List mounts  →  $effect: silo.list({})  →  _setItems

Navigate to Detail page
  └─ Detail mounts  →  $effect: silo.get(id)
  └─ Related List mounts (embedded)
       └─ $effect: silo.list({ fk_field: pk_value })  →  _mergeItems
```
