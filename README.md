# half-orm-gen

> **⚠️ Alpha — not for production.**  
> This project is under active development. APIs, generated code structure, and CLI
> commands may change without notice between releases. Do not use in production
> environments.

A [halfORM](https://github.com/half-orm/half-orm) extension that generates a
[Litestar](https://litestar.dev) or [FastAPI](https://fastapi.tiangolo.com) REST API
**and** a frontend backoffice ([SvelteKit 5](https://svelte.dev) or
[Angular](https://angular.dev)) from your [half-orm-dev](https://github.com/half-orm/half-orm-dev) project.

## Installation

```bash
pip install half-orm-gen
```

---

## API

```bash
# Litestar
half_orm gen api --litestar
litestar --app ho_api/app:application run --reload

# FastAPI
half_orm gen api --fastapi
uvicorn ho_api.app:application --reload
```

---

## Frontend backoffice

```bash
# SvelteKit 5
half_orm gen frontend --svelte
cd ho_frontend/svelte && npm install && npm run dev

# Angular
half_orm gen frontend --angular
cd ho_frontend/angular && npm install && npm start
```

---

## Contributing

We are looking for contributors with expertise in:

- **Angular** — improve generated components, routing, and state management
- **SvelteKit** — improve generated stores, layouts, and page components
- **Litestar** — improve the dynamic runtime, middleware, and OpenAPI integration
- **FastAPI** — improve the dynamic runtime and Pydantic integration

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a development environment
and the areas where help is most needed.

---

## Documentation

**Backend**
- [Litestar architecture](docs/backend/litestar/architecture.md) — runtime, CRUD_ACCESS, role system, WebSocket
- [Authorization](docs/backend/authorization.md) — JWT, roles, `/ho_access`, `/ho_setup`
- [CRUD access](docs/backend/crud-access.md) — access model, verbs, field access, `@ho_api_filter`, `@tools.api_*`
- [What goes in a relation class](docs/backend/relation-class-guide.md) — class vs. `ho_api/custom/`, the escape hatch
- [FastAPI architecture](docs/backend/fastapi/architecture.md) — status/parity with Litestar

**Frontend (shared)**
- [Frontend architecture](docs/frontend/architecture.md) — silo pattern, access map, live updates
- [Generated frontend code](docs/frontend/code-organization.md) — file layout, regenerated vs scaffolded
- [ResourceSilo reference](docs/frontend/resource-silo-reference.md) — full reactive API, one silo per app

**Angular**
- [Silo architecture](docs/angular/silo-architecture.md) — signals, data flow, deduplication
- [Access control](docs/angular/access-control.md) — reactive buttons, FK auto-resolve, dynamic roles, simulation

**Svelte**
- [Silo architecture](docs/svelte/silo-architecture.md) — runes, data flow, deduplication
- [Access control](docs/svelte/access-control.md) — reactive buttons, FK auto-resolve, dynamic roles

---

## See also

- [half-orm](https://github.com/half-orm/half-orm) — the PostgreSQL ORM at the core
- [half-orm-dev](https://github.com/half-orm/half-orm-dev) — the development framework
