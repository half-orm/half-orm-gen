> **Paused (this session)** — the user wants to first address a separate,
> more fundamental concern: separating generator (Python) code from the
> Angular/Svelte code it currently embeds as f-strings, before adding
> more code to the generators. See `planning/` for that design doc once
> written. This plan remains valid and should be resumed afterward.

# Contextual access configuration — replace the central admin matrix with inline, per-page editing (Angular only)

## Context

Today, configuring CRUD_ACCESS (who can GET/POST/PUT/DELETE which fields,
`fk_auto` rules, searchable fields, label fields) all happens in one
dedicated `/ho_bo/admin` page: pick a role in the left column, then a
big central matrix shows every resource, and clicking "▼ fields" opens
an inline editor panel. This is disconnected from where those same
fields are actually *used* — an admin configuring `blog.post.author_id`
has to leave the post list/detail entirely and navigate role → resource
→ verb → panel to find the same field again.

The user's objection (this session): for a UI, unlike a database, *the
place matters* — if a field is already shown somewhere (a list column, a
detail row, a create-form input), that's where it should be configurable
too, not behind a separate, disconnected admin section. This also
surfaces as a concrete blocker: `half_orm_meta.identity."user"` (added
this session as a GET-only FK-select target, see `planning/a_resoudre.md`
item 18) has no natural list/detail page of its own, which is part of why
configuring it centrally has been awkward. Moving configuration onto the
actual `blog.post` pages where `author_id` lives sidesteps that
entirely.

Decided this session: this redesign is **Angular-only**. Svelte has no
admin capability today (no `catalog`, no `simulateRole`, no
`PermissionsMatrixComponent` embedding — confirmed unused dead assets)
and stays that way; nothing here changes Svelte.

## What already exists (confirmed by exploration — reuse, don't rebuild)

- **`PermissionsMatrixComponent`/`PermissionsFieldsComponent`**
  (`half_orm_gen/frontend/angular/v19/_permissions_matrix.py`) — already
  embedded **read-only** on `list.component.ts`
  (`_list_component.py:257`, `@if (auth.isAdmin())`, not shown when
  `embedded()`) and `detail.component.ts` (`_detail_component.py:220-224`,
  same guard). **Not** embedded on the create form
  (`_form_components.py`'s `_create_component`) — needs adding.
  Clicking a role row already calls `auth.simulateRole(role)` /
  `exitSimulation()` — the "always-available role simulator" the user
  asked for already exists here, just needs to survive the redesign.
- **Backend admin-editing endpoints** (`half_orm_gen/backend/litestar/v2/ho_admin.py`)
  are already fully generic and resource-agnostic — nothing new needed:
  `POST/DELETE /ho_admin/access`, `POST/DELETE[/batch] /ho_admin/field_access_in`,
  `POST/DELETE[/batch] /ho_admin/field_access_out`,
  `POST/DELETE /ho_admin/field_access_fk_auto`,
  `POST/DELETE /ho_admin/field_access_searchable`,
  `POST/DELETE /ho_admin/field_label`.
- **`GET /ho_admin/catalog`** (`ho_admin.py` `ho_admin_catalog`) is already
  **resource-scoped**: one dict keyed by `schema/table`, each entry
  self-contained (`fields`, `label_fields`, `pk_fields`,
  `fields_with_defaults`, `fk_deps`, `dynamic_roles`, `filters`, `access`
  with per-verb-per-role `in`/`out`/`fk_auto`/`searchable`/
  `active_filters`/`inherited_in`/`inherited_out`). No role-selection step
  needed — `auth.catalog()[map_key]` alone is enough for a resource's own
  page to render and edit its full config.
- **Sidebar pattern to copy**: `_app_shell.py`'s `_app_component` already
  has two collapsible sections (`showFederationNav`/`showLocalNav`,
  plain boolean fields, default federation closed / resources open) and
  an existing `auth.isAdmin()` guard (used today for the bottom ⚙ Admin
  icon linking to `/ho_bo/admin`) — the same guard and toggle pattern
  applies directly to a new "Admin" section.
- **Gap found**: the `CatalogEntry` TS interface (`_app_shell.py:23-30`)
  is missing `fk_auto`, `searchable`, `inherited_in`, `inherited_out` on
  its `access` entries even though the backend already returns them —
  `_permissions_matrix.py` works around this today with a local
  `RoleVerbAccess` cast. Fix the real type instead of casting.

## Plan

### 1. Fix `CatalogEntry`'s `access` entry type (`_app_shell.py`)

Add `fk_auto`, `searchable`, `inherited_in`, `inherited_out` to the
per-role access entry shape so every consumer (permissions matrix,
future editors) can read them without casting.

### 2. Make the permissions matrix editable

In `_permissions_matrix.py`:
- Add a checkbox (not just ✓/—) per role×verb cell, wired to
  `POST /ho_admin/access` (grant) / `DELETE /ho_admin/access/{id}`
  (revoke) — reusing the exact payload shape `_ho_admin.py`'s
  `toggleAccess` already sends.
- Replace the hover-only tooltip with a click-to-open inline editor
  panel (same trigger cell, popover already wired) showing: in/out field
  checkboxes for POST/PUT/GET, an `fk_auto` radio group per FK field
  (`connected_user`/`context`/`select`), searchable checkboxes (GET),
  and label-field checkboxes (resource-level, not per-role, shown once).
  This is a **direct port** of `_ho_admin.py`'s existing panel logic
  (`panelAccess`, `toggleField`, `addAllFields`, `fkGroupsInPanel`,
  `getFkAutoRule`, `setFkAutoGroup`, `toggleFilter`, `toggleSearchable`,
  `labelFields`, `toggleLabelField`) — same methods, same endpoints,
  just parameterized by `(resource, verb, role)` read from the
  component's own `catalogEntry` input instead of a globally-selected
  role/panel signal.
- Keep the existing role-simulation trigger (click a role row) exactly
  as-is — it's the "always available" simulator the user wants, and it
  already works.

### 3. Embed the matrix on the create form too

`_form_components.py`'s `_create_component` gets the same
`<app-permissions-matrix [catalogEntry]="auth.catalog()[map_key] ?? null" />`
embedding already used on list/detail (`@if (auth.isAdmin())`).

### 4. Sidebar: add an "Admin" section, drop the bottom gear icon

In `_app_shell.py`'s `_app_component` template, add a third collapsible
section (same pattern as Federation/Resources) labelled "Admin", gated
by `auth.isAdmin()`, containing two links: "Roles" → `/ho_bo/admin/roles`,
"Peers" → `/ho_bo/admin/peers`. Remove the standalone ⚙ icon at the
bottom of the sidebar (superseded by this section).

### 5. Split `_ho_admin.py` into two slim pages, drop the central matrix

Replace the single `HoAdminComponent` with two smaller components:
- **`AdminRolesComponent`** (`/ho_bo/admin/roles`) — just the existing
  role list/create/delete UI (today's left-column Roles block), no
  matrix, no field-editor panel (that logic moved into
  `PermissionsMatrixComponent` in step 2).
- **`AdminPeersComponent`** (`/ho_bo/admin/peers`) — today's Peers
  block (list, self-card/export key, registration-key panel) as its own
  page's main content instead of a sidebar list + separate center panel.
  Peers has no "natural location" outside admin (unlike CRUD_ACCESS,
  which now lives on each resource's own pages), so it stays a
  dedicated admin page — just no longer sharing a page with Roles.

Update `_app_routes` (`_app_shell.py`) to register both new routes
(`adminGuard`-protected, same guard already used for `/ho_bo/admin`) in
place of the single `/ho_bo/admin` route.

### 6. Wiring (`angular.py`)

Update imports/writes: two new component files instead of
`ho_admin.component.ts`, new route registrations, `_create_component`
call site passes through whatever's needed for the matrix embedding
(already has `map_key`/schema/table in scope).

## Verification

1. `make demo-blog` (or `make demo`), open `/ho_bo/blog/post` as admin —
   confirm the permissions matrix now has checkboxes and an editable
   panel per role×verb, and toggling access/fields/fk_auto/searchable/
   label actually persists (reload the page, confirm it stuck) and
   matches what the old `/ho_bo/admin` panel used to do.
2. Open the create-post form — confirm the matrix now appears there too.
3. Confirm `/ho_bo/admin/roles` and `/ho_bo/admin/peers` both work,
   `adminGuard` still redirects non-admins, and the sidebar's new Admin
   section links to them; confirm the old bottom ⚙ icon is gone.
4. Confirm role simulation (clicking a role row in the matrix) still
   works exactly as before from any of list/detail/create.
5. Spot-check `half_orm_meta.identity/user`'s `author_id` FK config is
   now edited from `blog.post`'s own pages, with no separate resource
   entry needed anywhere in a central matrix.

## Critical files

- `half_orm_gen/frontend/angular/v19/_permissions_matrix.py` — matrix
  becomes editable, field-editor panel ported in
- `half_orm_gen/frontend/angular/v19/_ho_admin.py` — split into
  `AdminRolesComponent` + `AdminPeersComponent`, matrix/field-editor
  code removed (moved to `_permissions_matrix.py`)
- `half_orm_gen/frontend/angular/v19/_app_shell.py` — `CatalogEntry` type
  fix, sidebar Admin section, `_app_routes` updated
- `half_orm_gen/frontend/angular/v19/_form_components.py` — embed matrix
  on `_create_component`
- `half_orm_gen/frontend/angular/v19/angular.py` — wiring/imports for the
  two new admin components and routes
