# halfORM Backoffice — Generated frontend code organization

> See also: [architecture.md](architecture.md) for runtime principles,
> [../svelte/silo-architecture.md](../svelte/silo-architecture.md) and
> [../angular/silo-architecture.md](../angular/silo-architecture.md) for silo details.

Generated with:
```
half_orm gen frontend --svelte
half_orm gen frontend --angular
```

---

## Regenerated vs scaffolded once

| | Regenerated on every `gen frontend` | Scaffolded once (never overwritten) |
|---|---|---|
| **Svelte** | `src/lib/generated/` · `src/routes/(nav)/ho_bo/` | `src/lib/auth.svelte.ts` · `src/lib/stateRegistry.ts` · `src/lib/latex.ts` · `src/routes/+layout.svelte` · `src/routes/(nav)/+layout.svelte` · `src/routes/(nav)/login/` · `src/routes/(nav)/access/` · `src/routes/(nav)/schema/` |
| **Angular** | `src/app/generated/` · `src/app/app.routes.ts` | `src/app/core/` · `src/app/pages/` · `src/app/app.component.ts` · `src/app/app.config.ts` · `src/app/pages/schema/` |

**Consequence**: never edit files under `generated/` or the `ho_bo/` routes — they are
overwritten. Custom application code belongs outside these directories.

---

## Svelte — directory structure

```
src/
├── lib/
│   ├── auth.svelte.ts              ← scaffolded: auth state, WS, fetchedRoutes
│   ├── stateRegistry.ts            ← scaffolded: clearAllStates hook
│   ├── latex.ts                    ← scaffolded: LaTeX rendering helper
│   └── generated/
│       ├── stores/
│       │   ├── silo-registry.svelte.ts   ← REGENERATED: SiloRegistry singleton
│       │   ├── resource.silo.svelte.ts   ← REGENERATED: ResourceSilo class
│       │   ├── schema.types.ts           ← REGENERATED: HoMeta / ResourceSchema types
│       │   └── filters.ts                ← REGENERATED: filter helpers
│       └── components/
│           └── {schema}_{table}/         ← one directory per relation
│               ├── List.svelte
│               ├── DetailView.svelte
│               ├── Fields.svelte
│               └── CreateForm.svelte     ← absent for views (no PK / no POST)
└── routes/
    ├── +layout.svelte              ← scaffolded: root layout
    ├── +page.svelte                ← scaffolded: redirect to /ho_bo
    └── (nav)/
        ├── +layout.svelte          ← scaffolded: nav sidebar + auth guard
        ├── +layout.ts              ← scaffolded: registry.init()
        ├── login/+page.svelte      ← scaffolded
        ├── access/+page.svelte     ← scaffolded
        ├── schema/+page.svelte     ← scaffolded: navigable schema view (TOC + field details)
        └── ho_bo/
            └── {schema}/{table}/   ← REGENERATED: one SvelteKit route group per relation
                ├── +page.svelte    ← list page
                ├── [id]/+page.svelte   ← detail page
                └── new/+page.svelte    ← create page (absent for views)
```

---

## Angular — directory structure

```
src/app/
├── app.component.ts        ← scaffolded: shell + nav sidebar
├── app.config.ts           ← scaffolded: provideRouter, HttpClient, registry.init()
├── app.routes.ts           ← REGENERATED: all routes (list / detail / create per relation)
├── core/
│   ├── auth.service.ts     ← scaffolded: token, access, WS, fetchedRoutes
│   ├── auth.guard.ts       ← scaffolded: route guard
│   ├── state-registry.ts   ← scaffolded: clearAllStates hook
│   └── latex.pipe.ts       ← scaffolded: LaTeX rendering pipe
├── pages/
│   ├── login/              ← scaffolded
│   ├── home/               ← scaffolded
│   ├── access/             ← scaffolded
│   └── schema/             ← scaffolded: navigable schema view (TOC + field details)
└── generated/
    ├── silo-registry.service.ts  ← REGENERATED: SiloRegistry (@Injectable root)
    ├── resource.silo.ts          ← REGENERATED: ResourceSilo class (signals)
    ├── schema.types.ts           ← REGENERATED: HoMeta / ResourceSchema types
    ├── stores/
    │   └── filters.ts            ← REGENERATED: filter helpers
    └── components/
        └── {schema}_{table}/     ← one directory per relation
            ├── list.component.ts
            ├── detail.component.ts
            ├── fields.component.ts
            └── create.component.ts   ← absent for views
```

---

## Per-relation components — roles and reuse

Each relation generates up to four components. They are thin wrappers around the silo and
can be imported in custom pages as-is or used as starting points.

### `Fields` / `fields.component`

Read-only display of a single row's fields. Renders FK values as links and optionally the
PK as a link to the detail page.

**Props / inputs**:
- `item` — the row to display (required)
- `hidePk` (Svelte) / `[hidePk]` (Angular) — show PK as a non-linked span instead of a
  link (default: `false`)

**Use case**: embed in a custom detail page to show a related object inline, or as a
read-only summary card anywhere in the application.

### `List` / `list.component`

Paginated, sortable, filterable list backed by the resource silo.

**Props / inputs**:
- `filters` — `Record<string, any>` of column values to pre-filter (default: `{}`)
- `embedded` — `boolean`, hides the search bar, URL sync and the Create button when `true`
  (default: `false`)

**Use case**: embed in a custom page to show a subset of rows without navigating to the
full list. Pass `filters={{ project_id: someId }}` and `embedded` to show only related
rows.

### `DetailView` / `detail.component`

Full detail view: left column shows the row's fields (with FK links), right column shows
Direct References (FK targets) and Related cards (reverse-FK lists).

**Props / inputs**:
- `id` — PK string (simple) or `col1:val1::col2:val2` (composite)

**Use case**: the backoffice detail page. Can also be imported in a custom page that needs
a rich read-only view of an object.

### `CreateForm` / `create.component`

Form for creating a new row. On success, navigates to the new row's detail page.

Absent for views (relations without a PK or without `POST` in `CRUD_ACCESS`).

---

## Accessing a silo directly

There is one generated `ResourceSilo` class per app (`resource.silo.ts` /
`resource.silo.svelte.ts` above) — every table's silo is an instance of that
same class, parameterized by its schema. The full reactive API it exposes
(state, access control, data operations) is documented once, for every
table, in [resource-silo-reference.md](resource-silo-reference.md).

Custom components can read from and write to any resource silo without going through a
generated component:

**Svelte**:
```typescript
import { registry } from '$lib/generated/stores/silo-registry.svelte.ts';
const silo = registry.get('public/project');
// silo.items, silo.byId, silo.list({...}), silo.get(id), ...
```

**Angular**:
```typescript
private registry = inject(SiloRegistry);
readonly silo = computed(() => this.registry.get('public/project'));
// this.silo().items(), this.silo().byId(), this.silo().list({...}), ...
```

---

## Views (SQL views, no PK)

Relations backed by a SQL view rather than a table generate only a `List` component and
a list route — no `DetailView`, `Fields`, or `CreateForm`, since there is no primary key
to navigate to and no INSERT/UPDATE/DELETE.
