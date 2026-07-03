# Contributing to half-orm-gen

half-orm-gen is an alpha project and contributions are very welcome, especially from
developers familiar with the frameworks it targets.

---

## Areas where help is most needed

| Domain | What we need |
|---|---|
| **Angular** | Improve generated components (list, detail, create, fields), routing, state management with signals, accessibility, UX polish |
| **SvelteKit** | Improve generated stores (silo pattern), layouts, page components, Svelte 5 runes adoption |
| **Litestar** | Improve the dynamic runtime (`backend/litestar/v2/runtime.py`): middleware, OpenAPI config, WebSocket handling, production hardening |
| **FastAPI** | Improve the dynamic runtime (`backend/fastapi/v0/runtime.py`): Pydantic models, lifespan, middleware integration |
| **Python / halfORM** | Route introspection (`backend/crud_routes.py`), CRUD_ACCESS logic, composite PK support |

You do not need to know Python to contribute to the Angular or Svelte generators — the
generated TypeScript templates live entirely in `frontend/angular/v19/` and
`frontend/svelte/v5/` as Python string constants.

---

## Dev environment setup

**Requirements**: Python ≥ 3.10, PostgreSQL, Node.js ≥ 22.

```bash
git clone https://github.com/half-orm/half-orm-gen
cd half-orm-gen
pip install -e ".[dev]"   # or: pip install -e . half-orm half-orm-dev litestar
```

Verify the install:

```bash
python -c "from half_orm_gen.frontend.angular.v19.angular import AngularAppGenerator; print('OK')"
python -c "from half_orm_gen.backend.litestar.v2.runtime import build_crud_app; print('OK')"
```

---

## Running the end-to-end demo

The `tests/e2e/scripts/` directory contains shell scripts that create a complete
halfORM project, generate the API and frontend, and run them.

```bash
cd tests/e2e/scripts
bash demo_blog.sh           # create DB, generate everything
bash demo_blog.sh --cleanup # drop DB and remove generated files
```

---

## Code structure

```
half_orm_gen/
├── backend/
│   ├── api_routes.py          ← @api_* decorated method route builder
│   ├── crud_routes.py         ← CRUD_ACCESS introspection → route definitions
│   ├── generate.py            ← GenApi: orchestrates scaffolding
│   ├── litestar/v2/
│   │   ├── runtime.py         ← build_crud_app() — dynamic Litestar app
│   │   ├── scaffold.py        ← writes ho_api/app.py
│   │   └── templates.py       ← Litestar code-gen templates
│   └── fastapi/v0/
│       ├── runtime.py         ← build_crud_app() — dynamic FastAPI app
│       ├── scaffold.py        ← writes ho_api/app.py
│       └── templates.py       ← FastAPI code-gen templates
└── frontend/
    ├── __init__.py            ← GenApp / GenStore
    ├── base.py                ← StoreGenerator base class
    ├── templates_filters.ts   ← shared TS filter helpers
    ├── angular/v19/
    │   ├── angular.py         ← AngularAppGenerator.generate()
    │   ├── _app_shell.py      ← auth service, app component, routes, login, access
    │   ├── _list_component.py ← list.component.ts/html/css
    │   ├── _detail_component.py
    │   ├── _form_components.py
    │   ├── _pages.py          ← home, schema pages
    │   ├── _static.py         ← package.json, angular.json, tsconfig, …
    │   └── *.ts               ← silo-registry, resource.silo, schema.types
    └── svelte/v5/
        ├── svelte.py          ← SvelteAppGenerator.generate()
        ├── svelte_store.py    ← stores-only generator
        └── *.ts               ← silo-registry, resource.silo, schema.types
```

### Key concepts

**Backend**: `build_crud_app(model)` reads `CRUD_ACCESS` from each relation module at
startup and registers Litestar/FastAPI route handlers dynamically — no per-relation code
generation. The generated `ho_api/app.py` is always overwritten; developer customisations
go in `ho_api/custom/` files that are never touched by the generator.

**Frontend**: `StoreGenerator.generate(classes, api_version, output_dir)` iterates over
all model classes and writes TypeScript files. Each framework subclass overrides `generate`.
The silo pattern (`ResourceSilo` / `SiloRegistry`) provides shared state for all
generated components.

---

## Adding a new backend framework

1. Create `backend/<framework>/v<N>/` with `__init__.py`, `runtime.py`, `scaffold.py`,
   `templates.py`.
2. `runtime.py` must expose `build_crud_app(model, ...) -> <App>`.
3. `scaffold.py` must expose `scaffold_api_dir(api_dir, module_name, api_version)` —
   writes `ho_api/app.py` with conditional imports for customisation.
4. Wire it in `backend/generate.py` alongside the `litestar`/`fastapi` dispatch.

## Adding a new frontend framework

1. Create `frontend/<framework>/v<N>/` with `__init__.py` and a generator module.
2. Subclass `StoreGenerator` from `frontend/base.py` and implement `generate(...)`.
3. Add a `--<framework>` option in `cli_extension.py`.

---

## Architecture docs

Detailed architecture documentation lives in `docs/`:

- [backend/litestar/architecture.md](docs/backend/litestar/architecture.md) — runtime, CRUD_ACCESS, role system
- [backend/crud-access.md](docs/backend/crud-access.md) — CRUD_ACCESS, @ho_api_filter, @tools.api_* reference
- [backend/authorization.md](docs/backend/authorization.md) — JWT, roles, @ho_api_role
- [backend/relation-class-guide.md](docs/backend/relation-class-guide.md) — what goes in a relation class vs. ho_api/custom/
- [frontend/architecture.md](docs/frontend/architecture.md) — silo pattern, access map, WS
- [frontend/code-organization.md](docs/frontend/code-organization.md) — generated file layout
- [frontend/resource-silo-reference.md](docs/frontend/resource-silo-reference.md) — full ResourceSilo reactive API
- [angular/silo-architecture.md](docs/angular/silo-architecture.md)
- [svelte/silo-architecture.md](docs/svelte/silo-architecture.md)

---

## Release process

```bash
make build    # runs on main branch only, requires clean repo
make publish  # uploads to PyPI via twine
```
