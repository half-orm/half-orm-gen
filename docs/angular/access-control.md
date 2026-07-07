# Angular frontend — Access control

## Overview

> Auth service and JWT: [backend/authorization.md](../backend/authorization.md)  
> Silo architecture: [internals/angular-silo-architecture.md](../internals/angular-silo-architecture.md)  
> Svelte equivalent: [svelte/access-control.md](../svelte/access-control.md)

Access control in the Angular frontend is driven by the `/ho_access` endpoint, which returns
the effective access map for the current JWT. The `AuthService` stores this map and exposes
it as a signal (`effectiveAccess`). Each `ResourceSilo` derives reactive access signals from
it at construction time.

---

## Auth signals (`AuthService`)

> Full member list (session, WS, simulation, route guards):
> [frontend/auth-service-reference.md](../frontend/auth-service-reference.md)

| Signal | Type | Description |
|---|---|---|
| `token` | `Signal<string \| null>` | Current JWT, or `null` if anonymous. |
| `userId` | `computed<string \| null>` | Decoded `sub` claim from JWT. |
| `displayName` | `computed<string>` | User's name (from `/ho_users`), or `'anonymous'`. |
| `isAdmin` | `computed<boolean>` | True if the user has the admin flag. |
| `effectiveAccess` | `computed<Record<string, any>>` | Active access map — own or simulated role. |

---

## ResourceSilo access API

> Full member list (this table plus data operations, state, URL builders):
> [frontend/resource-silo-reference.md](../frontend/resource-silo-reference.md)

### Static access (role-level)

These signals are computed once per silo from `auth.effectiveAccess()`.

| Member | Type | Description |
|---|---|---|
| `canCreate` | `Signal<boolean>` | True if POST is available for this resource. |
| `inaccessibleFields(verb?)` | method → `Set<string>` | Fields to hide for `verb` (`'GET' \| 'POST' \| 'PUT'`, default `'GET'`). GET: not in the effective `out` list. POST: not in `in`, plus `fk_auto` fields of type `connected_user`/`context`. PUT: not in `in` (or a matching dynamic role's `put_in`), plus **all** `fk_auto` fields. |
| `fkAutoFields(verb)` | method → `Record<string, string>` | FK auto-resolve rules for `verb` (`'POST' \| 'PUT'`, no default — always explicit): `{ field: 'connected_user' \| 'context' \| 'select' }`. |

### Per-row access (dynamic roles)

Dynamic roles attach to specific rows at query time (e.g. `post_author` applies only to posts
the user authored). The backend returns `meta.dynamic_roles` alongside each list response.

| Method | Signature | Description |
|---|---|---|
| `canAccess` | `(verb: string, id: string) → boolean` | True if the role has static access **or** a dynamic role grants `verb` for this `id`. |
| `canCreateWithFilters` | `(filters: Record<string, unknown>) → boolean` | True if POST is available **and** all `context` FK fields are present in `filters`. |

### Reactive button patterns

```angular
<!-- Delete button — per-row dynamic check -->
@if (silo.canAccess('DELETE', getPkId(item))) {
  <button (click)="handleDelete(getPkId(item), $event)">Delete</button>
}

<!-- Edit button — per-row dynamic check -->
@if (silo.canAccess('PUT', id)) {
  <button (click)="editing.set(!editing())">Edit</button>
}

<!-- New button — requires context FK fields in filters -->
@if (silo.canCreateWithFilters(filters())) {
  <a [routerLink]="['/ho_bo/schema/table/new']" [queryParams]="fkNewQueryParams()">New</a>
}

<!-- Conditional field in form -->
@if (!silo.inaccessibleFields('POST').has('title')) {
  <input [(ngModel)]="form['title']" name="title" />
}
```

---

## FK auto-resolve

Three resolver types control how FK fields behave in create forms:

| Type | Form visibility | Value source |
|---|---|---|
| `connected_user` | Hidden | Backend injects PK of the authenticated user (from JWT). |
| `context` | Hidden | Frontend sends value from current embedded list `filters` (query param on New URL). |
| `select` | Visible — `<select>` dropdown | User picks from list of target resource. |

### `context` injection in create form

When the user clicks **New** from an embedded list, the list passes context FK fields as
query params (e.g. `/ho_bo/blog/comment/new?post_id=<uuid>`). The create form reads them
back in `handleSubmit`:

```typescript
const fkAuto = this.silo.fkAutoFields('POST');
for (const [field, rule] of Object.entries(fkAuto)) {
  if (rule === 'context') {
    const val = this.route.snapshot.queryParamMap.get(field);
    if (val != null) payload[field] = val;
  }
}
```

### `connected_user` injection

Done server-side in the POST handler. The frontend never sends this field — it is stripped
from the payload and replaced with `str(request.state.user)` (UUID from JWT `sub` claim).

### `select`

The create form renders a `<select>` populated from the target resource's own silo
(`registry.get(targetKey).list()`, fetched once per form via a `fkAutoFields('POST')`-driven
effect). Options are labeled with the target resource's admin-configured label fields
(see [ResourceSilo reference — per-table variation](../frontend/resource-silo-reference.md)
and the Admin UI's "Label fields" panel), falling back to the raw PK if none are configured.
Edit (PUT) forms don't support `select` yet — every `fk_auto` field is currently hidden in
PUT regardless of type. Tracked as a fast-follow.

---

## Dynamic roles

Dynamic roles are resolved per-row by a custom Python function registered in the backend
(e.g. `post_author` checks whether `author_id == current_user`). The backend returns:

```json
"meta": {
  "dynamic_roles": {
    "post_author": { "ids": ["uuid-1", "uuid-2"], "verbs": ["PUT", "DELETE"] }
  }
}
```

The silo stores this in `dynamicRoles` (signal). `canAccess(verb, id)` checks both the static
access map and `dynamicRoles`:

```typescript
canAccess(verb: string, id: string): boolean {
  if (!!(this.auth.effectiveAccess() as any)[this.key]?.[verb]) return true;
  return Object.values(this.dynamicRoles()).some(
    rd => (rd as any).verbs.includes(verb) && (rd as any).ids.includes(id)
  );
}
```

---

## Role simulation (admin only)

An admin can temporarily simulate any role via the Admin UI. `auth.simulateRole(role)` fetches
the simulated access map from `/ho_admin/simulate-access?role=<name>` and stores it in
`auth.simulatedAccess`. `auth.effectiveAccess` returns `simulatedAccess ?? access`, so all
silo signals and buttons update automatically. A banner is shown while simulation is active.

```typescript
auth.simulateRole('anonymous');   // all silos now reflect anonymous's access
auth.exitSimulation();            // returns to real access
```
