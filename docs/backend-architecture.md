# halfORM Backoffice — Backend architecture

> Frontend consumption of this API: [frontend-architecture.md](frontend-architecture.md)  
> Svelte silo details: [svelte-silo-architecture.md](svelte-silo-architecture.md)  
> Angular silo details: [angular-silo-architecture.md](angular-silo-architecture.md)  
> Authorization setup: [authorization.md](authorization.md)

Two API frameworks are supported, selected at generation time:

```
half_orm gen api --litestar    # default — dynamic runtime, no per-relation code
half_orm gen api --fastapi     # legacy  — generates api/app.py with all routes inline
```

---

## Litestar (default)

The backend is a **Litestar** application built dynamically at startup from a halfORM model.
No code is generated per relation — routes are registered at runtime by reading
`CRUD_ACCESS` from each relation module.

**File**: `half_orm_gen/backend/litestar/v2/runtime.py`  
**Entry point**: `build_crud_app(model, module_name, api_version, middleware, route_handlers, **litestar_kwargs)`

`half_orm gen api --litestar` writes `ho_api/app.py` on every run (always regenerated).
The file imports `build_crud_app` and uses conditional imports for developer customisations:

```python
try:
    from ho_api.custom.middlewares.authorization import Authorization
    _middleware = [Authorization]
except ImportError:
    pass

try:
    from ho_api.custom.routes import routes as _route_handlers
except ImportError:
    pass

application = build_crud_app(MODEL, ..., middleware=_middleware, route_handlers=_route_handlers)
```

Developer-owned files (`custom/middlewares/authorization.py`, `custom/routes.py`) are never
touched by the generator — create them manually when needed.

## FastAPI

`half_orm gen api --fastapi` also regenerates `ho_api/app.py` on every run.
Custom routes are passed via `extra_routers`:

```python
try:
    from ho_api.custom.routes import router as _custom_router
    _extra_routers = [_custom_router]
except ImportError:
    pass

application = build_crud_app(MODEL, ..., extra_routers=_extra_routers)
```

**File**: `half_orm_gen/backend/fastapi/v0/runtime.py`  
**Entry point**: `build_crud_app(model, module_name, api_version, extra_routers, **fastapi_kwargs)`

The FastAPI path uses `half_orm_gen/backend/crud_routes.py` (route builder) and
`half_orm_gen/backend/fastapi/v0/templates.py` (code templates). These files are not
involved in the Litestar path.

---

The rest of this document describes the **Litestar runtime** (`backend/litestar/v2/runtime.py`).

---

## Route structure

All endpoints are versioned under `/v{api_version}` (e.g. `/v0`).

### Per-relation endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/{schema}/{table}` | List rows (paginated, filterable). |
| `GET` | `/{schema}/{table}/{id}` | Fetch a single row by PK. |
| `POST` | `/{schema}/{table}` | Create a row. |
| `PUT` | `/{schema}/{table}/{id}` | Update a row. |
| `DELETE` | `/{schema}/{table}/{id}` | Delete a row + WS cascade. |

Routes are only registered for verbs declared in `CRUD_ACCESS` (see below). In dev mode,
all verbs are registered for every relation even without `CRUD_ACCESS`.

### Special endpoints

| Path | Description |
|---|---|
| `GET /ho_meta` | Full schema metadata for all relations (fields, PKs, FKs). Sourced from `model.ho_meta()`. |
| `GET /ho_access` | CRUD access map filtered for the caller's roles. |
| `GET /ho_roles` | List of all declared roles (excludes `anonymous`). |
| `WS /ws` | WebSocket endpoint for live mutation events. |

---

## CRUD_ACCESS configuration

> The access map built from `CRUD_ACCESS` is served to frontends via `GET /ho_access` —
> see [frontend-architecture.md — CRUD API](frontend-architecture.md#crud-api)
> for how frontends use it to gate UI actions.

Each relation module (`api/<module>/<schema>/<table>.py`) may declare:

```python
CRUD_ACCESS = {
    'GET':    { 'role_name': None },          # None = all fields allowed
    'POST':   { 'role_name': {'in': [...], 'out': [...]} },
    'PUT':    { 'role_name': {'in': [...], 'out': [...]} },
    'DELETE': { 'role_name': None },
}

API_EXCLUDED_FIELDS = ['internal_col', ...]   # never exposed in any verb
```

`CRUD_ACCESS` keys are HTTP verbs; values are dicts of `{ role: access_spec }`.

`access_spec` can be:
- `None` — unrestricted (all non-excluded fields).
- A list of field names — restricted output (`GET`) or input (`POST`/`PUT`).
- A dict `{ 'in': [...], 'out': [...], 'filter': {...} }` — explicit in/out fields plus
  an optional server-side row filter applied to every query.

If a relation module has no `CRUD_ACCESS`, no routes are registered in production.
In dev mode, routes are still registered with empty access dicts (see `dev_fallback`).

---

## Role system

### Role resolution

Every request resolves a list of authorized roles via `_get_roles(request)`:

1. Check `request.state.authorized_roles` — set by a real auth middleware if present.
2. Fall back to using the Bearer token value directly as the role name, appending
   `'anonymous'` (authenticated roles always inherit anonymous permissions).
3. No token → `['anonymous']`.

This fallback (token = role name) is intentional for development and **must be replaced**
by a real JWT middleware before production deployment. `build_crud_app` raises `RuntimeError`
at startup if the model is in production mode while the dev helpers are still active.

### Role-based field filtering

- **`_effective_out_fields(crud_access, verb, roles)`** — returns the union of allowed
  output fields across all matching roles, or `None` if no role matches (→ deny).
- **`_effective_in_fields(crud_access, verb, roles)`** — returns the union of allowed
  input fields; ignores roles not listed for this verb.
- **`_get_role_filter(crud_access, verb, roles)`** — returns a server-side filter dict
  merged from all matching roles (e.g. `{'owner_id': '<user_id>'}`) injected into the
  halfORM query.

---

## Request handlers — implementation pattern

All handler factories (`_make_list_handler`, `_make_get_handler`, etc.) follow the same
pattern:

1. A plain `async def handler(...)` closure capturing `cls`, `crud_access`, `api_excluded`,
   and PK metadata.
2. `handler.__name__` and `handler.__qualname__` are set to a unique slug before the Litestar
   decorator is applied — this ensures unique `operationId` values in the generated OpenAPI
   schema.
3. The Litestar route decorator (`@get`, `@post`, etc.) is applied last and the decorated
   function is returned.

### List handler

- Accepts `limit`, `offset`, `q` (search string), `fields` (projection), and
  `ho_col_<field>=<value>` column-filter query params.
- `q` syntax: `col:val` (prefix ilike), `col:>=val`, `col:>=val<=val` (range).
- Role filter is merged into the halfORM constructor kwargs.
- Returns `{ data: [...], meta: { offset, limit, has_more } }`.

### Get / Put / Delete handlers

- PK is always passed as a plain string (`{id:str}`) in the URL path.
- Simple PKs: passed directly to the halfORM constructor.
- Composite PKs: decoded from `col1:val1::col2:val2` format via `_parse_composite_pk`.

---

## Composite primary keys

URL format: `col1:val1::col2:val2` (each pair separated by `:`, pairs by `::`).

`_parse_composite_pk(pk_str, expected_cols)` validates the format, splits it, and returns
`{ col: val, ... }`. Returns HTTP 400 on malformed input or unexpected column names.

---

## WebSocket live updates

> Frontend consumption: [frontend-architecture.md — Live updates](frontend-architecture.md#live-updates--websocket)

The `_ConnectionManager` singleton holds the set of active WebSocket connections.
After every mutating operation a `broadcast` is sent:

```json
{ "event": "create" | "update" | "delete", "resource": "schema/table", "id": "<pk>" }
```

### Cascade on delete

The HTTP DELETE handler returns **204 No Content**. Cascade notifications are sent
exclusively via WebSocket in the following order:

1. `_ws_broadcast_cascade` walks the reverse FK tree **recursively**, querying child rows
   before the SQL DELETE runs. For each child row it recurses into grandchildren first, then
   broadcasts `{ "event": "delete", "resource": "child_schema/child_table", "id": "..." }`.
2. `ho_adelete` executes the SQL DELETE (the DB cascade-deletes the children).
3. A final `{ "event": "delete", "resource": "...", "id": "..." }` is broadcast for the
   directly deleted row.

Each frontend silo subscribed to the affected resource key receives its own `delete` event
and removes the row from its `byId` and `items` — so **all silos are cleaned up
automatically** without any extra HTTP request.

Only relations with a simple PK registered in `ws_rmap` participate in the cascade
broadcast. Composite-PK relations are skipped.

---

## Application bootstrap (`build_crud_app`)

```
for cls in model.classes():
  ├─ import module  →  read CRUD_ACCESS, API_EXCLUDED_FIELDS
  ├─ resolve schema/table/path/pk_info
  ├─ build access_map entry  (used by /ho_access)
  ├─ populate roles_set      (used by /ho_roles)
  ├─ register ws_rmap entry  (used by delete cascade)
  └─ register route handlers for declared verbs
       (+ all verbs in dev_fallback mode)

assemble Litestar(
  special_handlers    # ho_meta, ho_roles, ho_access, ws
  + relation_handlers # per-relation CRUD
  + route_handlers    # ho_api/custom/routes.py (optional, passed from app.py)
)
```

### Dev mode vs production

| Behaviour | Dev | Production |
|---|---|---|
| Routes without `CRUD_ACCESS` | Registered (all verbs) | Not registered |
| Bearer token = role name | Active | Must be replaced by JWT middleware |
| `ho_roles`, `ho_access` | Available | Available (but access map may be empty) |

---

## Custom routes

Drop a `routes` list in `ho_api/custom/routes.py`:

```python
from litestar import get

@get('/my-custom-endpoint')
async def my_handler() -> dict:
    return {'hello': 'world'}

routes = [my_handler]
```

`ho_api/app.py` imports this list conditionally — if the file is absent the import silently
fails and no custom routes are added. The file is never touched by the generator.

For FastAPI, expose an `APIRouter` as `router` instead:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get('/my-custom-endpoint')
async def my_handler() -> dict:
    return {'hello': 'world'}
```
