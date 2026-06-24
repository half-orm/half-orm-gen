# halfORM Backoffice — Frontend architecture

This document covers the principles shared by both the Svelte and Angular frontends.
For framework-specific details see:
- [svelte-silo-architecture.md](svelte-silo-architecture.md)
- [angular-silo-architecture.md](angular-silo-architecture.md)

For the generated file structure and reusable components see:
- [frontend-code-organization.md](frontend-code-organization.md)

For the backend that exposes the API consumed here see:
- [backend-architecture.md](backend-architecture.md)

---

## CRUD API

> Backend reference: [backend-architecture.md — Route structure](backend-architecture.md#route-structure)

The backend exposes one set of REST endpoints per database relation:

| Method | Path | Description |
|---|---|---|
| `GET` | `/{schema}/{table}` | List rows. Supports `offset`, `limit`, `q` (search), and `ho_col_<field>=<value>` filter params. |
| `GET` | `/{schema}/{table}/{pk}` | Fetch a single row by primary key. |
| `POST` | `/{schema}/{table}` | Create a row. |
| `PUT` | `/{schema}/{table}/{pk}` | Update a row. |
| `DELETE` | `/{schema}/{table}/{pk}` | Delete a row. |

All endpoints are versioned under a prefix (e.g. `/v0`). Two special endpoints exist:

| Path | Description |
|---|---|
| `GET /ho_meta` | Full schema metadata: fields, PK, FK deps, reverse FKs for all relations. |
| `GET /ho_access` | Allowed operations per relation for the current token. |

Column filter parameters are prefixed with `ho_col_` to avoid collisions with internal
parameters (`q`, `offset`, `limit`). Example: filter on `project_id` →
`?ho_col_project_id=<uuid>`.

Composite primary keys are encoded in URL paths as `col1:val1::col2:val2`.

---

## Silo pattern — data memoization

Each relation has a **ResourceSilo**: a reactive store that holds all rows fetched so far
for that resource. There is one silo per resource per session; it accumulates data across
navigation.

```
┌─────────────────────────────────────────┐
│             ResourceSilo                │
│  items   — ordered list (unfiltered)    │
│  byId    — Map<pk, row> (all fetched)   │
│  isLoading / hasMore / currentOffset    │
└─────────────────────────────────────────┘
```

Two write paths exist:

- **`setItems(data)`** — called for unfiltered list fetches (no params, offset 0). Replaces
  the full `items` and rebuilds `byId`.
- **`mergeItems(data)`** — called for filtered fetches, load-more, or FK-filtered embedded
  lists. Adds new rows to `byId` and rebuilds `items` from it. Filtered results therefore
  accumulate alongside the unfiltered ones in the same silo.

The `SiloRegistry` is a singleton initialised once at app boot from `/ho_meta`. It holds all
silos and exposes `get(key)` / `tryGet(key)`.

---

## Route cache — avoiding redundant fetches

`AuthService` / `AuthState` holds a plain `Set<string>` called `fetchedRoutes`. Before any
HTTP call the silo checks this set and skips the request if the exact URL has already been
fetched. The URL is added to the set immediately (before the response arrives) to prevent
concurrent duplicates.

```
silo.list(params)
  ↓
build url (baseUrl + ho_col_* params + limit/offset)
  ↓
fetchedRoutes.has(url) ?  →  yes: return (no-op)
  ↓  no
fetchedRoutes.add(url)        ← guard before await
  ↓
HTTP GET  →  mergeItems / setItems
```

Additional guard: `loadedFilters` (per silo, keyed by `JSON.stringify(params)`) tracks
filter combinations where the API returned `has_more: false`. Once a filter set is fully
loaded its key is set in `loadedFilters` and subsequent calls with the same params are
skipped at the top of `list()`, before even building the URL.

The route cache (`fetchedRoutes`) is **not reactive** — it is a plain `Set`, not a signal or
`$state`. This is intentional: it is a deduplication guard, not observable state. It is
cleared on login and logout (along with silo data via `clearAllStates()`).

`clearAllStates()` calls `silo.clear()` on every registered `ResourceSilo`, flushing
`items`, `byId`, and `loadedFilters`. The `SiloRegistry` itself is **not** reset: its
`_ready` flag, the silos Map, and the `meta` signal all survive login/logout. Only the
data inside each silo is flushed.

---

## Live updates — WebSocket

> Backend reference: [backend-architecture.md — WebSocket live updates](backend-architecture.md#websocket-live-updates)

The backend pushes mutation events over a WebSocket at `/v0/ws`:

```json
{ "event": "create" | "update" | "delete", "resource": "schema/table", "id": "<pk>" }
```

Each silo subscribes to these events at construction time (for the lifetime of the app).
On receipt:

- `delete` → remove the row from `items` and `byId` immediately. On a cascading DELETE the
  backend pre-broadcasts one `delete` event per affected child row (across all resources)
  before the SQL runs, so every silo cleans itself up without any extra HTTP request.
- `create` / `update` → call `GET /{schema}/{table}/{id}` to refresh the single row, then
  update `byId` and `items` in place.

The WebSocket reconnects automatically with a 2-second backoff on close or error.

---

## Interaction between the three mechanisms

```
User visits Detail page for resource A (pk = X)
  │
  ├─ silo_A.get(X)
  │    └─ byId has X?  →  yes: return cached
  │                    →  no: GET /A/X  →  setItem  →  byId updated
  │
  └─ Related card for resource B (fk_field = X) mounts
       └─ silo_B.list({ fk_field: X })
            ├─ loadedFilters has key?  →  skip
            ├─ fetchedRoutes has url?  →  skip
            └─ GET /B?ho_col_fk_field=X&limit=100
                 └─ mergeItems  →  byId_B updated
                      └─ displayItems (computed/derived) filters byId_B in memory  →  card fills in

Meanwhile, another user creates a row in B
  └─ WS event { event: "create", resource: "B", id: Y }
       └─ silo_B.refresh(Y)  →  GET /B/Y  →  setItem  →  card updates reactively
```
