# half-orm-gen

> **⚠️ Alpha — not for production.**  
> This project is under active development. APIs, generated code structure, and CLI
> commands may change without notice between releases. Do not use in production
> environments.

A [halfORM](https://github.com/half-orm/half-orm) extension that generates a
[Litestar](https://litestar.dev) REST API
**and** a frontend backoffice ([SvelteKit 5](https://svelte.dev) or
[Angular](https://angular.dev)) from your [half-orm-dev](https://github.com/half-orm/half-orm-dev) project.

## Installation

```bash
pip install half-orm-gen
```

---

## API

```bash
half_orm gen api --litestar
litestar --app ho_api/app:application run --reload
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a development environment
and the areas where help is most needed.

---

## Documentation

**Authentication**
- [Overview](docs/authentication/overview.md) — authentication vs authorization, env vars, file map
- [Local authentication](docs/authentication/local-auth.md) — `identity.user`, `local_auth.py`, HS256/RS256 signing
- [Federation](docs/authentication/federation.md) — sharing identities across independently-deployed peers

**Backend**
- [Authorization](docs/backend/authorization.md) — JWT, roles, `/ho_access`, `/ho_setup`
- [CRUD access](docs/backend/crud-access.md) — access model, verbs, field access, `@ho_api_filter`, `@tools.api_*`
- [What goes in a relation class](docs/backend/relation-class-guide.md) — class vs. `ho_api/custom/`, the escape hatch

**Frontend (shared)**
- [Generated frontend code](docs/frontend/code-organization.md) — file layout, regenerated vs scaffolded
- [ResourceSilo reference](docs/frontend/resource-silo-reference.md) — full reactive API, one silo per app
- [AuthService / AuthState reference](docs/frontend/auth-service-reference.md) — session, WS, simulation, route guards

**Angular**
- [Access control](docs/angular/access-control.md) — reactive buttons, FK auto-resolve, dynamic roles, simulation

**Svelte**
- [Access control](docs/svelte/access-control.md) — reactive buttons, FK auto-resolve, dynamic roles

**Internals** — half-orm-gen's own implementation, for maintaining/extending the generator itself
- [Litestar architecture](docs/internals/litestar-architecture.md) — runtime, CRUD_ACCESS, role system, WebSocket
- [Frontend architecture](docs/internals/frontend-architecture.md) — silo pattern, access map, live updates
- [Angular silo architecture](docs/internals/angular-silo-architecture.md) — signals, data flow, deduplication
- [Svelte silo architecture](docs/internals/svelte-silo-architecture.md) — runes, data flow, deduplication

---

## See also

- [half-orm](https://github.com/half-orm/half-orm) — the PostgreSQL ORM at the core
- [half-orm-dev](https://github.com/half-orm/half-orm-dev) — the development framework
