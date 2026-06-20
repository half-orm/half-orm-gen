# half-orm-gen

A [halfORM](https://github.com/half-orm/half-orm) extension that generates a
[Litestar](https://litestar.dev) or [FastAPI](https://fastapi.tiangolo.com) REST API
**and** a frontend backoffice ([SvelteKit 5](https://svelte.dev) or
[Angular](https://angular.dev)) from your halfORM project.

## Installation

```bash
pip install half-orm-gen
```

---

## API

```bash
# Litestar
half_orm gen api --litestar
litestar --app api.app:application run --reload

# FastAPI
half_orm gen api --fastapi
uvicorn api.app:application --reload
```

---

## Frontend backoffice

```bash
# SvelteKit 5
half_orm gen frontend --svelte
cd frontend/svelte && npm install && npm run dev

# Angular
half_orm gen frontend --angular
cd frontend/angular && npm install && npm start
```

---

## See also

- [half-orm](https://github.com/half-orm/half-orm) — the PostgreSQL ORM at the core
- [half-orm-dev](https://github.com/half-orm/half-orm-dev) — the development framework
