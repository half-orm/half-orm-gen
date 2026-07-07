# Svelte frontend — Access control

## Overview

> Auth store and JWT: [backend/authorization.md](../backend/authorization.md)  
> Silo architecture: [internals/svelte-silo-architecture.md](../internals/svelte-silo-architecture.md)  
> Angular equivalent: [angular/access-control.md](../angular/access-control.md)

Access control in the Svelte frontend is driven by the `/ho_access` endpoint, which returns
the effective access map for the current JWT. The `AuthState` singleton stores this map as
`$state`. Each `ResourceSilo` derives reactive access from it using `$derived`.

> **Note**: The Svelte frontend does not include an Admin UI. Access configuration
> (roles, field access, FK auto-resolve) is managed exclusively via the Angular admin UI.

---

## Auth state (`AuthState`)

> Full member list (session, WS, route guards):
> [frontend/auth-service-reference.md](../frontend/auth-service-reference.md)

| Field | Type | Description |
|---|---|---|
| `token` | `string \| null` (`$state`) | Current JWT, or `null` if anonymous. |
| `userId` | `string \| null` (`$derived`) | Decoded `sub` claim from JWT. |
| `displayName` | `string` (`$derived`) | User's name (from `/ho_users`), or `'anonymous'`. |
| `isAdmin` | `boolean` (`$derived`) | True if the user has the admin flag. |
| `access` | `Record<string, any>` (`$state`) | Active access map from `/ho_access`. |

---

## ResourceSilo access API

> Full member list (this table plus data operations, state, URL builders):
> [frontend/resource-silo-reference.md](../frontend/resource-silo-reference.md)

### Static access (role-level)

These are `$derived` values computed from `auth.access`.

| Member | Type | Description |
|---|---|---|
| `canCreate` | `boolean` (`$derived`) | True if POST is available for this resource. |
| `inaccessibleFields(verb?)` | method → `Set<string>` | Fields to hide for `verb` (`'GET' \| 'POST' \| 'PUT'`, default `'GET'`). GET: not in the effective `out` list. POST: not in `in`, plus `fk_auto` fields of type `connected_user`/`context`. PUT: not in `in` (or a matching dynamic role's `put_in`), plus **all** `fk_auto` fields. |
| `fkAutoFields(verb)` | method → `Record<string, string>` | FK auto-resolve rules for `verb` (`'POST' \| 'PUT'`, no default — always explicit): `{ field: 'connected_user' \| 'context' \| 'select' }`. |

### Per-row access (dynamic roles)

| Method | Signature | Description |
|---|---|---|
| `canAccess` | `(verb: string, id: string) → boolean` | True if the role has static access **or** a dynamic role grants `verb` for this `id`. |
| `canCreateWithFilters` | `(filters: Record<string, unknown>) → boolean` | True if POST is available **and** all `context` FK fields are present in `filters`. |

### Reactive button patterns

```svelte
<!-- Delete button — per-row dynamic check -->
{#if silo.canAccess('DELETE', String(item.id))}
  <button onclick={() => handleDelete(item.id)}>Delete</button>
{/if}

<!-- Edit button — per-row dynamic check -->
{#if silo.canAccess('PUT', id)}
  <button onclick={() => editing = !editing}>Edit</button>
{/if}

<!-- New button — requires context FK fields in filters -->
{#if silo.canCreateWithFilters(filters)}
  <a href={fkNewUrl()}>New</a>
{/if}

<!-- Conditional field in form -->
{#if !silo.inaccessibleFields('POST').has('title')}
  <input bind:value={form.title} name="title" />
{/if}
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
const urlParams = new URLSearchParams(window.location.search);
for (const [field, rule] of Object.entries(silo.fkAutoFields('POST'))) {
  if (rule === 'context') {
    const val = urlParams.get(field);
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
`$effect`). Options are labeled with the target resource's admin-configured label fields
(see [ResourceSilo reference](../frontend/resource-silo-reference.md) and the Angular Admin
UI's "Label fields" panel — Svelte has no Admin UI, per the note above), falling back to
the raw PK if none are configured.

Edit (PUT) forms don't support `select` yet — every `fk_auto` field is currently hidden in
PUT regardless of type. Tracked as a fast-follow.

---

## Dynamic roles

Dynamic roles are resolved per-row by a custom Python function registered in the backend.
The backend returns `meta.dynamic_roles` alongside each list response:

```json
"meta": {
  "dynamic_roles": {
    "post_author": { "ids": ["uuid-1", "uuid-2"], "verbs": ["PUT", "DELETE"] }
  }
}
```

The silo stores this in `dynamicRoles` (`$state`). `canAccess(verb, id)` checks both the
static access map and `dynamicRoles`:

```typescript
canAccess(verb: string, id: string): boolean {
  if (!!(auth.access as any)[this.key]?.[verb]) return true;
  return Object.values(this.dynamicRoles).some(
    rd => rd.verbs.includes(verb) && rd.ids.includes(id)
  );
}
```
