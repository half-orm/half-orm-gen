# Federation — delegation protocol internals

> Using federation (enabling it, registering peers, env vars): [../authentication/federation.md](../authentication/federation.md)  
> Local authentication basics: [../authentication/local-auth.md](../authentication/local-auth.md)  
> Full design rationale and rejected alternatives: [`planning/identite_federee.md`](../../planning/identite_federee.md)

This page documents *how* the cross-peer login delegation is implemented —
the generated code, the exact message sequence, and the security properties
it relies on. It's aimed at maintaining or extending half-orm-gen's
federation feature itself, not at using it in a generated project (for
that, see [federation.md](../authentication/federation.md)).

---

## The delegation protocol

Terminology: **B** is the peer someone is trying to log into; **A** is the
peer they already have an account on and choose to authenticate via.

Who picks the peer? The person, explicitly — B's login page shows "Sign in
via: [A] [...]" buttons (one per trusted peer) alongside its own local
form, if any. No automatic routing by email domain or other heuristic.

1. The person clicks "Sign in via A" on B's frontend.
2. B's frontend redirects the browser to
   `${B_api}/auth/login?peer=${A_id}&return_to=${B_frontend}/auth/callback`
   — `A_id` is A's own `HO_PEER_ID` (uuid), never a free-text name (see
   [federation.md — Registering a peer](../authentication/federation.md#registering-a-peer)
   and [identite_federee.md §4bis](../../planning/identite_federee.md#4bis-enregistrement-des-peers--carte-auto-descriptive-2026-07-06)
   for why: B couldn't reliably know what *name* A goes by, since names
   are self-declared and never chosen by whoever registers a peer — but
   B always knows A's `id`, because that's exactly what got imported when
   B registered A's card).
3. B's backend (`federation.py`'s `auth_login`, "requesting" branch — a
   `peer` param is present) looks up that `id` in its own `peer` table
   (must be `trusted`), generates a random single-use `state`, stores it
   server-side (`login_state`: which peer was targeted, where to return
   to), and redirects the browser to
   `${A_api}/auth/login?redirect_uri=${B_api}/auth/callback&csrf_state=${state}`.
4. A's backend (same `auth_login` handler, "serving" branch —
   `redirect_uri`+`csrf_state` are present instead of `peer`) redirects
   the browser to **A's own frontend**, `${A_frontend}/auth/delegate`,
   carrying the same `redirect_uri`+`csrf_state`.
5. A's frontend (`/auth/delegate` page) checks whether this browser tab
   already holds a valid token for A (`AuthService`/`AuthState`'s
   `sessionStorage`-backed session). If so, it skips the form entirely and
   forwards that existing token straight away — same-tab SSO shortcut, see
   [Known limitation](#known-limitation-partial-single-sign-on) below.
   Otherwise it shows the ordinary login form; the person authenticates
   **on A's domain** — their credentials never touch B. Either way, once a
   token is available, the page redirects the browser to
   `${redirect_uri}?token=${A_token}&csrf_state=${state}` — no separate
   signing step, since a login token issued under `HO_JWT_ALGORITHM=RS256`
   is already signed with A's private key (see
   [local-auth.md](../authentication/local-auth.md#rs256-federation-only-opt-in)).
6. B's callback route (`federation_callback`) retrieves `state` from
   `login_state` (must exist, not expired, **not already consumed** — it's
   deleted immediately on read), verifies the token's signature against
   **A's specific registered public key** (never "any trusted peer's"),
   upserts `half_orm_meta.identity.user` (`origin_peer_id` = A), mints B's
   **own** local session token — with roles looked up from **B's own**
   `half_orm_meta.api.user_role` for this `sub` (`['connected']` if none
   yet), exactly like a plain local login; identity federates, the role
   *grant* does not (see [federation.md — reference demo](../authentication/federation.md#reference-demo-blog_demo--pages_demo)) —
   and redirects to the original `return_to` with that token.
7. The frontend's `/auth/callback` page (already existed before
   federation, also used for plain local login flows) reads the `token`
   query param and calls `AuthService.setToken`.

```
Person  ──▶ B frontend "Sign in via A"
        ──▶ GET B_api/auth/login?peer=<A_id>                 (B: requesting)
        ──▶ redirect: A_api/auth/login?redirect_uri=B_api/auth/callback&csrf_state=s
        ──▶ redirect: A_frontend/auth/delegate?redirect_uri=...&csrf_state=s   (A: serving)
        ──▶ POST A_api/auth/login {email, password}          ← credentials stay on A
        ──▶ redirect: B_api/auth/callback?token=<A-signed jwt>&csrf_state=s
        ──▶ redirect: B_frontend/auth/callback?token=<B-signed jwt>
        ──▶ AuthService.setToken(...)  — signed in on B
```

---

## Security properties

- **`csrf_state` is the only anti-CSRF protection** — without it, an
  attacker could trick a victim into completing a login flow the attacker
  initiated (potentially binding the victim's session to an attacker-
  controlled account).
- **Single-use, time-limited**: deleted the moment it's read; rejected if
  older than 10 minutes (`_STATE_TTL_SECONDS`).
- **Signature checked against the specific peer targeted by this
  `state`**, never "any trusted peer" — otherwise a different (still
  trusted) peer could substitute its own token for someone else's login
  attempt.
- **`redirect_uri` is implicit, not attacker-supplied**: B's backend
  builds it itself from `HO_PEER_URL`; it's never taken from user input
  or an untrusted query param. This matters because an unvalidated
  redirect target combined with an already-authenticated session on A
  could otherwise let an attacker exfiltrate a validly-signed identity
  token to a site of their choosing.
- **No credential relay**: A's password is checked only by A's own
  backend. B never receives or transmits it — this is a deliberate
  browser-redirect design (closer to OIDC/SAML) instead of a
  server-to-server relay where the local peer would retransmit
  credentials it collected itself.
- **HTTPS required** on every hop in production (redirects, callback) —
  tokens and state travel as URL query params, which must never cross an
  unencrypted network. Local development over plain HTTP is the one
  exception.

### Known limitation: partial single sign-on

Step 5's auto-forward (2026-07-06) only covers **the same browser tab
still holding A's token in `sessionStorage`** — e.g. you signed into A
earlier in this tab, then click "sign in via A" on B without having
navigated away from A's origin in between. It does **not** cover:
navigating to B directly (bypassing the delegation entry point
entirely — see [federation.md](../authentication/federation.md) for why
that's a separate concern from this protocol), a different tab, a
different browser, or after `sessionStorage` was cleared (tab closed,
private browsing). In those cases the login form still appears. A real
cross-tab/cross-device SSO would need a server-side session mechanism
(cookies) instead of a token in per-tab storage — not implemented.

---

## Generated `ho_api/federation.py`

Two handlers, both requiring `HO_JWT_ALGORITHM=RS256` (raises at import
time otherwise):

```python
@get('/auth/login')
async def auth_login(
    peer: str | None = None, return_to: str = '/',
    redirect_uri: str | None = None, csrf_state: str | None = None,
) -> Redirect:
    ...  # branches on which params are present — see protocol above
```

A single path handles both directions of the protocol — "this project's
own `/auth/login`" is the one fixed URL every peer redirects to, whether
this project is the requester or the identity source. (The query parameter
is named `csrf_state`, not `state` — Litestar reserves the name `state` for
its own injected `litestar.datastructures.State` app-state object.)

```python
@get('/auth/callback')
async def federation_callback(token: str, csrf_state: str) -> Redirect:
    ...  # validate state, verify signature, upsert user, mint local token
```

Both are appended to `_route_handlers` in `ho_api/app.py` alongside your
`custom/routes.py` routes, and mounted under the API version prefix like
everything else.

---

## Frontend routes

Scaffolded once (not regenerated), same convention as the rest of
`AuthService`/`AuthState` — see
[auth-service-reference.md](../frontend/auth-service-reference.md):

| Route | Angular file | Svelte file | Purpose |
|---|---|---|---|
| `/auth/callback` | `pages/auth-callback/auth-callback.component.ts` | `routes/auth/callback/+page.svelte` | Reads `token` from the query string, calls `setToken`, navigates home. Used both for the plain login/signup flow and as the tail end of a federated delegation. |
| `/auth/delegate` | `pages/auth-delegate/auth-delegate.component.ts` | `routes/auth/delegate/+page.svelte` | Shown when **this** peer is acting as the identity source for someone logging into another peer. A small self-contained email/password form; posts to this project's own `POST /auth/login`, then forwards the resulting token to `redirect_uri`. Requires `redirect_uri`+`csrf_state` query params — shows an error if reached without them. |

`AuthService.loginUrlForPeer(peerId)` (Angular) / the Svelte equivalent
builds the initiating link — `peerId` is the target's `id` from
`GET /auth/peers` (its `HO_PEER_ID`), not its display `name`:

```ts
loginUrlForPeer(peerId: string): string {
  const returnTo = `${window.location.origin}/auth/callback`;
  return `${API_BASE}/auth/login?peer=${encodeURIComponent(peerId)}&return_to=${encodeURIComponent(returnTo)}`;
}
```

### Cross-site navigation (`federationNavUrl`)

The sidebar's "Federation" section (one link per trusted peer, opening
their own frontend) doesn't just link to the target's homepage — it
constructs a delegation-initiating URL on the **target's own API**
directly, as if the person had clicked "sign in via `<this peer>`" on the
target's login page themselves, skipping that extra step:

```ts
federationNavUrl(peer: { url: string; frontend_url: string | null }): string {
  if (!peer.frontend_url) return peer.url;               // no friendly page to land on
  const localId = this.localPeerId;                       // this project's own HO_PEER_ID
  if (!localId) return `${peer.frontend_url}/ho_bo`;       // not federation-enabled itself
  const returnTo = `${peer.frontend_url}/auth/callback`;
  return `${peer.url}/auth/login?peer=${encodeURIComponent(localId)}&return_to=${encodeURIComponent(returnTo)}`;
}
```

This only works because delegation is looked up **by id**, not by name
(see [federation.md — registering a peer](../authentication/federation.md#registering-a-peer)):
this project knows its own `HO_PEER_ID` unambiguously (exposed as
`local_id` in `GET /auth/peers`), and that's exactly the value the target
peer stored when it registered this project's card — so this project can
construct the target's own `/auth/login?peer=<localId>` URL correctly
without ever needing to know what name (or anything else) the target
calls it. Landing on the target still requires *it* to have registered
*this* project's card too (bilateral, never automatic — see
[federation.md](../authentication/federation.md#registering-a-peer)); if
it hasn't, the target's `auth_login` responds `404 Unknown or untrusted
peer` and the browser simply shows that instead of a redirect chain.
