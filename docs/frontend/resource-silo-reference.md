# ResourceSilo reference

> Angular usage: [angular/access-control.md](../angular/access-control.md)  
> Svelte usage: [svelte/access-control.md](../svelte/access-control.md)  
> File layout: [code-organization.md](code-organization.md)  
> Internals (dedup, WebSocket lifecycle): [angular/silo-architecture.md](../angular/silo-architecture.md), [svelte/silo-architecture.md](../svelte/silo-architecture.md)

---

## One class, every table

There is **one** generated `ResourceSilo` class per app —
`generated/resource.silo.ts` (Angular) or
`generated/stores/resource.silo.svelte.ts` (Svelte) — not one per table.
`SiloRegistry.get('schema/table')` returns an instance of that same class,
parameterized at construction time by a `ResourceSchema` object sourced from
`GET /ho_meta`. Every resource's silo exposes the exact same API — this page
documents it once, instead of per table or per framework.

```typescript
// Angular
private registry = inject(SiloRegistry);
readonly silo = computed(() => this.registry.get('blog/post'));

// Svelte
import { registry } from '$lib/generated/stores/silo-registry.svelte.ts';
const silo = registry.get('blog/post');
```

Angular exposes reactive members as **signals** (call with `()`); Svelte
exposes them as **runes** (read as plain properties, no `()`) — noted per
member below. Methods that take arguments (`canAccess`, `inaccessibleFields`,
`list`, `get`, ...) are called the same way in both frameworks.

---

## State

| Member | Angular | Svelte | Description |
|---|---|---|---|
| `items` | `Signal<Row[]>` | `Row[]` (`$state`) | Currently loaded rows. |
| `byPk` | `Signal<Map<string, Row>>` | `Map<string, Row>` (`$state`) | Loaded rows indexed by PK string. |
| `isLoading` | `Signal<boolean>` | `boolean` (`$state`) | True while a `list`/`loadMore` request is in flight. |
| `hasMore` | `Signal<boolean>` | `boolean` (`$state`) | True if another page may be available. |
| `currentOffset` | `Signal<number>` | `number` (`$state`) | Offset to use for the next `loadMore`. |
| `filters` | `Signal<Record<string,string>>` | `Record<string,string>` (`$state`) | Last filter set passed to `list`. |
| `selectedId` | `Signal<string \| null>` | `string \| null` (`$state`) | Set by generated list components on row click; free for custom use. |
| `sortField` / `sortAsc` | `Signal<string \| null>` / `Signal<boolean>` | `string \| null` / `boolean` (`$state`) | Current client-side sort column/direction. |
| `dynamicRoles` | `Signal<Record<string, {ids, verbs, put_in?, put_out?}>>` | same shape (`$state`) | Per-row dynamic role grants from the last response's `meta.dynamic_roles`. |

---

## Access control

The full detail on what these compute from and how FK auto-resolve/dynamic
roles feed them lives in [angular/access-control.md](../angular/access-control.md)
/ [svelte/access-control.md](../svelte/access-control.md) — this table is the
canonical member list.

| Member | Angular | Svelte | Description |
|---|---|---|---|
| `canCreate` | `Signal<boolean>` | `boolean` (`$derived`) | True if POST is available for this resource. |
| `inaccessibleFields(verb?)` | method, `Set<string>` | method, `Set<string>` | Fields to hide for `verb` (`'GET' \| 'POST' \| 'PUT'`, default `'GET'`). GET: not in the effective `out` list. POST: not in `in`, plus `fk_auto` fields of type `connected_user`/`context`. PUT: not in `in` (falling back to a matching dynamic role's `put_in`), plus **all** `fk_auto` fields. |
| `fkAutoPostFields` / `fkAutoPutFields` | `Signal<Record<string,string>>` | `Record<string,string>` (`$derived`) | FK auto-resolve rule per field: `'connected_user' \| 'context' \| 'select'`. |
| `searchableFields` | `Signal<string[]>` | `string[]` (`$derived`) | Fields the current role may filter on via `q=`. |
| `canAccess(verb, id)` | method → `boolean` | method → `boolean` | True if static access grants `verb`, **or** a dynamic role grants `verb` for this row `id`. |
| `canCreateWithFilters(filters)` | method → `boolean` | method → `boolean` | True if `canCreate` **and** every `context`-type FK field is present in `filters`. |

Call `inaccessibleFields()` with no argument for the GET/read case — that's
the default, matching how `canAccess` always takes its verb explicitly but
`inaccessibleFields` is read far more often in the GET context (list/detail
views) than POST or PUT:

```typescript
silo.inaccessibleFields()          // GET — same as inaccessibleFields('GET')
silo.inaccessibleFields('POST')
silo.inaccessibleFields('PUT')
```

---

## URL builders

| Member | Signature | Description |
|---|---|---|
| `listUrl` | `(params?: Row) => string` | Builds the list endpoint URL with query params. |
| `getUrl` | `(id: string) => string` | Builds the single-row endpoint URL. |

---

## Data operations

| Member | Signature | Description |
|---|---|---|
| `list` | `(params?, offset?) => void` (Angular) / `=> Promise<void>` (Svelte) | Fetches a page; deduped per exact URL via `fetchedRoutes`. |
| `loadMore` | `(params?) => void` | Fetches the next page using `currentOffset`. |
| `resetFilterState` | `() => void` | Clears the dedup cache and pagination state (call before changing filters and re-`list`ing). |
| `get` | `(id: string) => Observable<Row \| null>` (Angular) / `=> Promise<Row \| null>` (Svelte) | Returns a cached row if present, otherwise fetches it. |
| `refresh` | `(id: string) => Observable<Row \| null>` / `=> Promise<Row \| null>` | Always fetches, updates the cache, merges `dynamic_roles`. |
| `create` / `update` / `remove` | `(data)` / `(id, data)` / `(id)` | Raw HTTP calls — do not touch local state; call `setItem`/`removeItem` yourself or `refresh` after. |
| `setItem` / `removeItem` | `(item)` / `(id)` | Insert/update or remove a single row in `items`/`byPk` without a network call. |
| `clear` | `() => void` | Empties `items`/`byPk` and resets pagination. Called automatically on logout via `registerClear`. |

---

## Identity helper

| Member | Signature | Description |
|---|---|---|
| `pkValue` | `(item: Row) => string \| null` | Extracts this resource's PK as a string (handles composite PKs), or `null` if the schema has no PK. |

---

## Companion `AuthService`/`AuthState` members

Read alongside a silo's access members, not instead of them — full list in
[angular/access-control.md](../angular/access-control.md#auth-signals-authservice)
/ [svelte/access-control.md](../svelte/access-control.md#auth-state-authstate):
`token`, `resourceAccessVersion()[key]` (Angular) / equivalent invalidation
in Svelte, `simulatedRole()`/simulation state, `accessVersion()`,
`fetchedRoutes` (request dedup set shared across silos), `wsEvent$`/`lastEvent`
(the live WebSocket event stream every silo subscribes to).

---

## Per-table vs. boilerplate in generated components

When customizing a generated `list`/`detail`/`create` component or writing
your own page against a silo, here's what actually varies per table versus
what's identical everywhere and safe to leave alone:

**Varies per table** (regenerated from the schema — this is what you'd
change if hand-rolling a page for a new table):
- The hardcoded field list (`fieldTypes` map in list components, the `form`
  object in detail/create components).
- One FK-auto-resolve `effect`/`$effect` per **outgoing** FK column — zero
  for a table with no FKs, one per FK otherwise (e.g. `blog/comment` has
  three: `author_id`, `post_id`, `comment_type`).
- Which `Fields`/`List` components get imported, for FK targets and
  reverse-FK relations.
- The `textFields`/`putTextFields` set (which fields get `'' → null`
  coercion on submit vs. passed through as text).

**Byte-for-byte generated, safe to ignore when customizing**: constructor
wiring, `handleUpdate`/`handleSubmit`, the infinite-scroll
`IntersectionObserver` setup, filter/sort/URL sync, and the `displayItems`
computed/`$derived` that combines `silo.items()` with local filters and
sort state.
