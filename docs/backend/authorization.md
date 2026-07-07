# Authorization

> Role declaration and CRUD_ACCESS: [crud-access.md](crud-access.md)  
> Backend runtime internals: [../internals/litestar-architecture.md](../internals/litestar-architecture.md)  
> How the JWT this page consumes gets minted in the first place: [../authentication/overview.md](../authentication/overview.md)

---

## Overview

Authorization in half-orm-gen is **role-based**: every request carries a list of active
roles and every route checks that list against `CRUD_ACCESS` before executing.

The framework generates a JWT middleware (`ho_api/authorization.py`) that decodes the
Bearer token and populates `request.state`. Developers customize the behavior via a
scaffolded hook file (`ho_api/custom/middlewares/jwt_config.py`).

---

## Built-in roles

| Role | Meaning |
|---|---|
| `anonymous` | No authentication. Always active. |
| `connected` | Any authenticated user. Inherits `anonymous`. |
| `admin` | Full backoffice access. Inherits `connected`. |

These three roles are guaranteed by the framework — they are inserted at gen time and at
server startup by `ensure_system_roles`. They cannot be deleted.

Domain roles (e.g. `author`) are stored in the `half_orm_meta.api.role` table.

---

## Role hierarchy and inheritance

Roles form a tree rooted at `anonymous`. When a request carries role `admin`, the backend
expands it to `['admin', 'connected', 'anonymous']` via `_expand_roles`. This means
`CRUD_ACCESS` entries declared for `connected` or `anonymous` are automatically granted
to `admin` requests.

---

## System tables (`half_orm_meta.api`)

### `role`

Stores the role hierarchy. Seeded automatically at startup.

```sql
CREATE TABLE "half_orm_meta.api".role (
    name        text PRIMARY KEY,
    parent_name text REFERENCES "half_orm_meta.api".role(name) ON DELETE SET NULL,
    deletable   boolean NOT NULL DEFAULT TRUE
);
```

### `user_role`

Associates an application user UUID with a role name.

```sql
CREATE TABLE "half_orm_meta.api".user_role (
    user_id   uuid NOT NULL,
    role_name text NOT NULL REFERENCES "half_orm_meta.api".role(name) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_name)
);
```

There is no FK to the application user table by default — add it after both tables exist:

```sql
ALTER TABLE "half_orm_meta.api".user_role
    ADD CONSTRAINT user_role_user_id_fk
    FOREIGN KEY (user_id) REFERENCES actor."user"(id) ON DELETE CASCADE;
```

---

## Generated JWT middleware

`half_orm gen api` always regenerates `ho_api/authorization.py`. It:

1. Reads `HO_JWT_SECRET` from the environment (raises `RuntimeError` at startup if absent).
2. Decodes the Bearer JWT on every request.
3. Sets `request.state.user = uuid.UUID(payload['sub'])`.
4. Sets `request.state.authorized_roles = payload.get('roles', ['connected'])`.
5. Calls `enrich_state(payload, state)` from `jwt_config.py` if provided.

`ho_api/.env` is scaffolded once with a random secret and loaded inline by `app.py` (no
external dependency). Add it to `.gitignore`.

### JWT payload

```json
{ "sub": "<user-uuid>", "roles": ["admin"] }
```

Only explicit roles are stored in the token. Route handlers expand the hierarchy via
`_expand_roles` at call time.

---

## Developer hook: `jwt_config.py`

`ho_api/custom/middlewares/jwt_config.py` is scaffolded once and never overwritten.
Implement `enrich_state` to add extra claims to `request.state`:

```python
async def enrich_state(payload: dict, state: dict) -> None:
    state['tenant_id'] = payload.get('tenant_id')
    state['email']     = payload.get('email')
```

---

## Dynamic roles (`@ho_api_role`)

A **dynamic role** is a role whose assignment depends on the row being accessed, not just
the user. Declare it with the `@ho_api_role` decorator in your relation module:

```python
from half_orm_gen.tools import ho_api_role

class Post(ho_baseclasses.BC_BlogPost):

    @ho_api_role('post_author')
    def _is_author(self, request, rows: list) -> set:
        user = request.state.user          # uuid.UUID from JWT
        return {row['id'] for row in rows if row['author_id'] == user}
```

**Contract:**
- `rows` — the list of dicts already fetched by the handler (max 100 for lists, 1 for PUT/DELETE).
- Returns a **set of PKs** from `rows` for which the current user has this role.

**Runtime behaviour:**
- At startup, `discover_and_register` scans all relation modules, registers methods in
  `_ROLE_REGISTRY`, and inserts the role name into `half_orm_meta.api.role` (marked
  `deletable=True`).
- **List handler** — calls each registered method after fetching rows; adds
  `meta.dynamic_roles: {role_name: [pk1, pk2, ...]}` to the response. The frontend uses
  this to show/hide per-row action buttons.
- **PUT handler** — calls each registered method with the fetched row (1-element list);
  adds matching role names to `authorized_roles` before the access check.
- Dynamic role methods are only called for authenticated requests (`request.state.user`
  must be set).

Configure access rights for dynamic roles in the admin UI exactly like static roles.

See also: [relation-class-guide.md](relation-class-guide.md) — what else belongs
on the relation class alongside `@ho_api_role`, and when it doesn't.

---

## First-run detection

`GET /ho_setup` → `{"has_admin": bool}` — generated route, no authentication required.

The frontend calls this on startup. If `has_admin` is `false`, it shows a signup form to
create the first admin account.

---

## Admin endpoints (`/ho_admin/*`)

The `/ho_admin/` sub-API lets an admin manage roles and CRUD access rules at runtime
without restarting the server.

| Method | Path | Description |
|---|---|---|
| `GET` | `/v0/ho_admin/catalog` | Full access catalog (all resources × all roles). |
| `GET` | `/v0/ho_admin/roles` | All declared roles with their parent. |
| `POST` | `/v0/ho_admin/roles` | Create a role. |
| `DELETE` | `/v0/ho_admin/roles/{name}` | Delete a role. |
| `POST` | `/v0/ho_admin/access` | Add an access rule. |
| `PUT` | `/v0/ho_admin/access/{id}` | Update an access rule. |
| `DELETE` | `/v0/ho_admin/access/{id}` | Remove an access rule. |

All `/ho_admin/` endpoints require `admin` in `_get_roles(request)`. A non-admin caller
receives:

```
HTTP 403 Admin access required (current roles: ['connected', 'anonymous'])
```

---

## Blog demo example

`blog_demo` demonstrates real local authentication end-to-end: signup/login
routes backed by bcrypt password hashes in
`half_orm_meta.identity."user"`, real JWTs, and (since it's generated with
`--federation`) an RS256 keypair shared with `pages_demo` — see
[authentication/local-auth.md](../authentication/local-auth.md) and
[authentication/federation.md](../authentication/federation.md) for the
full mechanism these routes rely on.

```
POST /auth/signup  {name, email, password}  →  create user; first signup becomes admin
POST /auth/login   {email, password}        →  checks password via local_auth.authenticate()
GET  /ho_users                              →  list users with is_admin flag
```

These routes (and the `_sign` helper signing with `HO_JWT_SECRET`/the RS256
private key depending on `HO_JWT_ALGORITHM`) are written by `demo_blog.sh`
(step 11) into `ho_api/custom/routes.py` — never hand-edit that generated
demo file; edit the script and regenerate (`make demo-blog`).

Fixture accounts and the `author_id` FK constraint are set up by
`fixtures/blog_demo_data.sql`.

The `post_author` dynamic role is declared in `blog_demo/blog/post.py` (injected by
`demo_blog.sh` step 11a) and allows post authors to edit their own posts.
