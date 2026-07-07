# Federated identity between peers

> Back to overview: [overview.md](overview.md)  
> Local authentication (HS256, `local_auth.py`, custom routes): [local-auth.md](local-auth.md)  
> How the delegation protocol works internally (steps, security, generated code): [../internals/federation-protocol.md](../internals/federation-protocol.md)  
> Full design rationale and rejected alternatives: [`planning/identite_federee.md`](../../planning/identite_federee.md)  
> Reference demo pair: `tests/e2e/scripts/demo_blog.sh` / `demo_pages.sh`, `make demo`

---

## Goal

Let several **independently deployed** half-orm-gen projects ("peers")
share the same person identities, without any central authority: any peer
can issue its own signed identity tokens, and any other peer can choose to
trust it explicitly. There is no "master" peer and no separate identity
service — every peer's own CRUD API doubles as its identity provider for
anyone who trusts it.

Enable it at generation time:

```bash
half_orm gen api --litestar --federation
```

This scaffolds an RS256 keypair, generates `ho_api/federation.py`, and adds
placeholder `HO_PEER_URL=` / `HO_FRONTEND_URL=` lines to `.env` for you to
fill in. Federation is additive — a federated project keeps its normal
local login (see [local-auth.md](local-auth.md)) unless you explicitly set
`HO_LOCAL_AUTH=none`.

A person signs in either locally (their own credentials on this project)
or "via" a trusted peer — the browser gets redirected to that peer's own
login, and comes back with a signed proof of identity. The full mechanics
of that redirect/callback round trip are in
[federation-protocol.md](../internals/federation-protocol.md); this page
only covers what you need to configure and operate it.

---

## The `half_orm_meta.identity` schema

Created by every project regardless of whether federation is enabled
(inert until you actually register a peer):

```sql
CREATE TABLE "half_orm_meta.identity".peer (
  id             uuid PRIMARY KEY,               -- the OTHER peer's own HO_PEER_ID — no DEFAULT
  name           text NOT NULL,                  -- the OTHER peer's own HO_PEER_NAME (display only)
  url            text NOT NULL,
  frontend_url   text,
  jwt_public_key text,
  trusted        boolean NOT NULL DEFAULT TRUE,
  created_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "half_orm_meta.identity"."user" ( ... );  -- see local-auth.md

CREATE TABLE "half_orm_meta.identity".login_state (
  state      text PRIMARY KEY,
  peer_id    uuid NOT NULL REFERENCES "half_orm_meta.identity".peer(id) ON DELETE CASCADE,
  return_to  text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- `peer` — every other project this one has been told to trust (or be
  trusted by). Registered manually, one row per direction — trust is
  **bilateral and explicit**, never inferred. `id`/`name` are the OTHER
  peer's own self-declared `HO_PEER_ID`/`HO_PEER_NAME` — never chosen
  here (see [Registering a peer](#registering-a-peer) below and
  [identite_federee.md §4bis](../../planning/identite_federee.md#4bis-enregistrement-des-peers--carte-auto-descriptive-2026-07-06)
  for why: a free-text local name can't be used as a reliable cross-peer
  lookup key). `jwt_public_key` is that peer's RS256 public key, needed to
  verify tokens it issues.
- `login_state` — server-side storage for the anti-CSRF state used during
  the delegation redirect. Single-use, short-lived, deleted as soon as
  it's consumed — see [federation-protocol.md](../internals/federation-protocol.md) for how.

---

## Registering a peer

No field is ever typed by hand on either side except the decision to
trust — registration is a single **registration key**: a `base64(JSON)`
blob one peer exports about itself, sent to the other peer's admin by
whatever channel they actually use (email, chat, ...) — the two admins
are not necessarily the same person in two browser tabs — and pasted
as-is once received. There's no signature on this blob (see
[identite_federee.md §4bis](../../planning/identite_federee.md#4bis-enregistrement-des-peers--carte-auto-descriptive-2026-07-06)
for why that's fine) — the trust comes from the channel used to hand the
string over, exactly like copying a public key by hand today, just
bundled into one paste instead of four separate fields. It does carry a
30-minute expiry (`expires_at`), since — unlike a same-session copy-paste
— the string may sit in an inbox for a while before the other admin acts
on it; regenerating one costs nothing (just reopen the admin page).

### Getting this project's own registration key

`GET /ho_admin/peer/self` (admin-only) returns a **freshly generated**
card every time it's called (no caching — its expiry starts from this
call):

```json
{
  "id": "b6e6...", "name": "blog_demo",
  "url": "http://localhost:8000/v0", "frontend_url": "http://localhost:4200",
  "algorithm": "RS256", "public_key": "-----BEGIN PUBLIC KEY-----...",
  "export_key": "eyJpZCI6ImI2ZTYuLi4iLCJuYW1lIjoi...=",
  "export_key_expires_at": "2026-07-06T12:34:56+00:00"
}
```

`export_key` is `base64(JSON({id, name, url, frontend_url, jwt_public_key, expires_at}))`
— the value to send to a trusted peer's admin. The Angular admin UI
(Peers panel, stacked under Roles in the same left column of
`/ho_bo/admin`) shows this as a "This peer" card with a "Copy
registration key" button — clicking it refetches this endpoint right
before copying, so the 30-minute window always starts fresh at copy
time, not at whenever the admin page happened to load. There is no
Svelte admin UI (Svelte has none at all — see
[access-control.md](../svelte/access-control.md)).

### Registering another peer here

`POST /ho_admin/peer` (admin-only): `{registration_key}` — the blob
received from the other peer's admin. The server decodes it, checks it
hasn't expired, and inserts exactly what it declares (`id`, `name`,
`url`, `frontend_url`, `jwt_public_key`) — nothing else to fill in beyond
deciding to paste it at all (`trusted` defaults to `true`).

```
GET/POST   /v0/ho_admin/peer            list / register (registration_key)
PUT        /v0/ho_admin/peer/{id}       update — {trusted} to toggle, or
                                         {registration_key} to re-import a
                                         rotated key (must match this id)
DELETE     /v0/ho_admin/peer/{id}       remove
```

Trust must be registered on **both sides** for a working round trip — A
trusting B lets B's users log into A; B must separately register and trust
A for the reverse.

### Public peer list

`GET /auth/peers` (unauthenticated) — used by the frontend login page to
render "Sign in via ..." buttons:

```json
{
  "peers": [{"id": "b6e6...", "name": "blog_demo", "url": "http://localhost:8000/v0", "frontend_url": "http://localhost:4200"}],
  "local_auth_enabled": true, "local_name": "pages_demo", "local_id": "a1f2..."
}
```

Only `trusted = true` peers are listed. `id` is what `loginUrlForPeer`
actually sends as `?peer=` (see
[federation-protocol.md](../internals/federation-protocol.md)) — `name` is
shown on the button, never used for the lookup. `local_auth_enabled`
reflects `HO_LOCAL_AUTH` — the frontend hides the email/password form
entirely when it's `false` (a federation-only peer). `local_name`/`local_id`
are THIS project's own `HO_PEER_NAME`/`HO_PEER_ID` — used to label the
local sign-in form ("Sign in on `<local_name>`") and to build the
cross-site navigation links in the sidebar's Federation section (see
[federation-protocol.md — cross-site navigation](../internals/federation-protocol.md#cross-site-navigation-federationnavurl)).

---

## Gotcha: the API version prefix

`HO_PEER_URL` and every registered `peer.url` must include the API version
prefix (`/v0` by default — see `_read_api_version()` in
`cli_extension.py`), because **every** route, including `federation.py`'s
own `/auth/login` and `/auth/callback`, is mounted under it:

```
HO_PEER_URL=http://localhost:8000/v0        # correct
HO_PEER_URL=http://localhost:8000           # wrong — /auth/login 404s
```

`HO_FRONTEND_URL` is the one exception — the frontend isn't API-versioned,
so it takes a bare origin (`http://localhost:4200`, no `/v0`).

---

## Reference demo: `blog_demo` + `pages_demo`

Two independent demo projects, different business domains (a blog vs a
wiki), federated with each other end to end:

```bash
make demo            # regenerates both + federates them (main entry point)
make demo-blog       # blog_demo only
make demo-pages      # pages_demo only
make demo-federate   # registers both as mutually trusted peers + loads
                      # pages_demo's fixture (blog_demo's real users
                      # pre-seeded in, as if delegated in already)
make demo-run         # start both APIs + both frontends
make demo-stop        # stop everything
```

`demo-federate` reads each project's **real, freshly generated** RS256
public key (`ho_api/public_key.pem`) and inserts it into the other's
`peer` table — so it must run after both `make demo-blog` and
`make demo-pages`. It also loads `fixtures/pages_demo_data.sql`, which
seeds pages_demo's `half_orm_meta.identity.user` with blog_demo's actual
user UUIDs (`origin_peer_id` pointing at blog_demo) — this gives
`wiki.page.author_id` a real, enforced foreign key to those identities
without requiring an actual browser round-trip through the delegation flow
just to set up demo data. Blog demo's admin account is separately granted
`admin` in pages_demo's own `user_role` — identity federates, the admin
*grant* does not (it's local per peer, exactly like any other role).

Both demo projects run their Angular frontend as the federation entry
point (`HO_FRONTEND_URL`) even though both Angular and Svelte are running
side by side — a peer only has one `HO_FRONTEND_URL`, so if you're testing
through the Svelte frontend and click "sign in via ...", the delegate page
that comes back is Angular's.
