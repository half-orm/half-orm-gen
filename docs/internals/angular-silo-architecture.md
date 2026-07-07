# Angular frontend — Silo architecture

## Overview

> General principles (silo pattern, route cache, WebSocket): [frontend-architecture.md](frontend-architecture.md)  
> Svelte equivalent: [svelte-silo-architecture.md](svelte-silo-architecture.md)  
> Backend API: [litestar-architecture.md](litestar-architecture.md)  
> Access control (signals, buttons, FK auto-resolve): [angular/access-control.md](../angular/access-control.md)  
> Looking for the full `ResourceSilo` member list instead of internals? [frontend/resource-silo-reference.md](../frontend/resource-silo-reference.md)

The Angular frontend uses a **silo-per-resource** pattern: one `ResourceSilo` instance per
database relation, all registered in a singleton `SiloRegistry` service. There is no Angular
service generated per-relation; only the per-relation components (List, Detail, Fields,
Create) are generated. The silo layer uses Angular `signal`s for reactivity.

---

## SiloRegistry

**File**: `src/app/generated/silo-registry.service.ts`

`@Injectable({ providedIn: 'root' })` — one instance for the entire app. Initialised once
on app boot by calling `registry.init(apiBase)`, which:

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

**File**: `src/app/generated/resource.silo.ts`

All fields declared with `signal(...)` are **Angular Signals** — reads inside `computed()`
or `effect()` are automatically tracked.

### Reactive state (signals)

| Field | Type | Description |
|---|---|---|
| `items` | `Signal<Row[]>` | Ordered list for the current unfiltered view. |
| `byId` | `Signal<Map<string, Row>>` | All fetched rows indexed by PK string. |
| `isLoading` | `Signal<boolean>` | True while a fetch is in flight. |
| `hasMore` | `Signal<boolean>` | Whether the API reported more pages. |
| `currentOffset` | `Signal<number>` | Next offset for `loadMore`. |
| `filters` | `Signal<Record<string, string>>` | Active local filter state (used by List for URL sync). |
| `selectedId` | `Signal<string \| null>` | Highlighted row id. |
| `sortField / sortAsc` | `Signal<string \| null> / Signal<boolean>` | Current sort column and direction. |

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
  ├─ [guard] isLoading()                                               → return (in-flight)
  │
  ├─ Build URL:  baseUrl + ?ho_col_<field>=<value>&...&limit=100[&offset=N]
  │
  ├─ [guard] auth.fetchedRoutes.has(url)                              → return (deduplicated)
  ├─  auth.fetchedRoutes.add(url)
  │
  ├─ http.get(url).subscribe(response => ...)
  │
  ├─ if params==={} && offset===0   → setItems(data)   (replaces items + byId)
  └─ else                           → mergeItems(data)  (adds to byId, rebuilds items)
```

### `setItems` vs `mergeItems`

- **`setItems`**: used for the plain unfiltered list. Replaces both `items` and `byId`.
- **`mergeItems`**: used for filtered results, load-more, and all FK-filtered embedded lists.
  Adds new rows into `byId`, then rebuilds `items` from `byId.values()`. This means
  filtered results accumulate in the same silo alongside the unfiltered ones — a single silo
  holds all rows ever fetched for that resource regardless of the filter used.

---

## Request deduplication: `auth.fetchedRoutes`

**File**: `src/app/core/auth.service.ts`

```typescript
readonly fetchedRoutes = new Set<string>();   // plain Set, not a signal
```

A plain (non-reactive) `Set` on the `AuthService` singleton. Before every fetch the silo
checks `fetchedRoutes.has(url)` and skips the request if true, then immediately adds the URL
before the Observable resolves. This prevents redundant network calls when multiple components
are initialised concurrently and request the same resource.

**Lifecycle**:

- Cleared via `fetchedRoutes.clear()` on `login()` and `logout()` (along with silo data
  via `clearAllStates()` which calls `silo.clear()` on every registered silo).
- **Not cleared on navigation** — persists for the entire session.

`silo.clear()` flushes `items`, `byId`, and `loadedFilters` inside each `ResourceSilo`.
The `SiloRegistry` itself is **not** reset on login/logout: `_ready`, the silos Map, and
`meta` all survive. Only the data inside each silo is flushed.

Because `fetchedRoutes` is a plain `Set` (not a signal), reading it inside a `computed()` or
`effect()` does **not** create a reactive dependency. This is intentional: the set is a
fire-and-forget dedup guard, not observable state.

---

## `displayItems` in List components

List components compute displayed rows client-side:

```typescript
displayItems = computed(() => {
  const filters = this.filters();
  const hasFilters = Object.keys(filters).length > 0;
  let items = hasFilters
    ? Array.from(this.silo().byId().values()).filter(item =>
        Object.entries(filters).every(([k, v]) => String(item[k]) === String(v)))
    : this.silo().items();
  // then apply localFilters and sort …
});
```

- **`hasFilters = true`** (embedded Related card with FK filter): scans `byId` in-memory.
  Data arrives when `silo.list(filters)` is called (via `effect`), completes, and
  `mergeItems` updates the `byId` signal. The `computed` recomputes automatically.
- **`hasFilters = false`** (standalone List page): uses `silo.items()` directly.

### Known limitation — empty Related cards on first load

Because `fetchedRoutes` is session-persistent, a filtered URL like
`/v0/public/foo?ho_col_bar=<id>&limit=100` is only fetched once. If the user navigates away
and back to the same detail page the silo already holds the data in `byId` (visible
immediately). But if it was never fetched at all the Related card will appear empty until
the `effect` fires and the HTTP call completes.

A subtler case: if `isLoading()` is true at mount time (another fetch is in flight for the
same silo), `list()` returns early. The card stays empty until the next reactive trigger
(e.g., `auth.token` signal update). Mitigation: call `silo.resetFilterState()` before
navigating to a detail page, or remove the `isLoading` guard for filtered calls.

---

## WebSocket live updates

> Backend reference: [litestar-architecture.md — WebSocket live updates](litestar-architecture.md#websocket-live-updates)

`AuthService.connectWs()` opens a WebSocket to `/v0/ws`. Each message is pushed to the
`wsEvent$` Subject. Every `ResourceSilo` subscribes in its constructor:

```typescript
this.auth.wsEvent$
  .pipe(filter(ev => ev.resource === key))
  .subscribe(ev => {
    if (ev.event === 'delete') this.removeItem(String(ev.id));
    else this.refresh(String(ev.id)).subscribe();
  });
```

The subscription is created at construction time and lives as long as the silo exists
(application lifetime).

---

## Lifecycle summary

```
App boot
  └─ SiloRegistry.init()  →  GET /ho_meta  →  create ResourceSilo × N
        └─ each silo subscribes to auth.wsEvent$ for live updates

Login / logout
  └─ auth.fetchedRoutes.clear()
  └─ clearAllStates()  →  silo.clear() × N   (items=[], byId=new Map(), loadedFilters.clear())
       SiloRegistry NOT reset — _ready/silos Map/meta persist

Navigate to List page
  └─ List mounts  →  effect: silo.list({})  →  setItems

Navigate to Detail page
  └─ Detail mounts  →  effect: silo.get(id).subscribe()
  └─ Related List mounts (embedded)
       └─ effect: silo.list({ fk_field: pk_value })  →  mergeItems
```
