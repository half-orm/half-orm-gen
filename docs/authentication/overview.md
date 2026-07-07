# Authentication

> Authorization (roles, CRUD_ACCESS) — a separate concern, built on top of this: [../backend/authorization.md](../backend/authorization.md)  
> Local authentication in depth: [local-auth.md](local-auth.md)  
> Cross-project federated identity: [federation.md](federation.md)  
> Frontend `AuthService`/`AuthState` reference: [../frontend/auth-service-reference.md](../frontend/auth-service-reference.md)

---

## Authentication vs authorization

These are two independent layers:

- **Authentication** — *who* is making this request? Answered by a JWT: every
  request carries a Bearer token, and the generated middleware
  (`ho_api/authorization.py`, despite the filename) decodes it into
  `request.state.user` (a UUID) and `request.state.authorized_roles`. This
  page and its children describe how that token gets minted in the first
  place, and by whom.
- **Authorization** — *what* can this user do? Answered by `CRUD_ACCESS`:
  role → resource → verb → field rules, evaluated on every route. See
  [authorization.md](../backend/authorization.md).

A request can be authenticated (has a valid token) without being authorized
for a given route, and vice versa (`anonymous` is itself a role, so
unauthenticated requests are still routed through the same authorization
check).

---

## Two ways to authenticate

| | Single project | Federated (multiple peers) |
|---|---|---|
| Enabled by | default | `half_orm gen api --litestar --federation` |
| JWT signing | `HO_JWT_ALGORITHM=HS256`, one shared secret | `HO_JWT_ALGORITHM=RS256`, one keypair per project |
| Who can verify tokens | anyone with the secret (symmetric) | anyone with the public key — but only this project can *sign* (asymmetric) |
| Login/signup | hand-written in `ho_api/custom/routes.py` (not generated) | same, plus a generated cross-peer delegation flow |
| Doc | [local-auth.md](local-auth.md) | [federation.md](federation.md) |

Federation is opt-in and additive: enabling it does not remove or replace
local authentication — it adds a second way for a *different* project's
users to sign in here, delegating to their home peer. A federated project
still has its own local login (unless explicitly disabled with
`HO_LOCAL_AUTH=none`), and still uses the same `half_orm_meta.identity.user`
table to record everyone it knows about, local or not.

---

## File map

| File | Status | Purpose |
|---|---|---|
| `ho_api/authorization.py` | always regenerated | JWT decode middleware — HS256 or RS256 depending on `HO_JWT_ALGORITHM` |
| `ho_api/local_auth.py` | always regenerated | `authenticate(model, email, password) -> uuid \| None` — pluggable, DB-backed by default |
| `ho_api/federation.py` | always regenerated, **only when `--federation`** | Cross-peer login delegation (`/auth/login`, `/auth/callback`) |
| `ho_api/custom/routes.py` | scaffolded once, **you write it** | Your actual `/auth/login`, `/auth/signup` route handlers |
| `ho_api/custom/middlewares/jwt_config.py` | scaffolded once | `enrich_state(payload, state)` hook — add extra claims to `request.state` |
| `ho_api/custom/local_auth.py.example` | scaffolded once, never imported | Template for a non-DB `authenticate()` (LDAP, ...) — copy to `local_auth.py` to activate |
| `ho_api/.env` | scaffolded once | Secret/keypair + all `HO_*` config below |
| `ho_api/private_key.pem` / `public_key.pem` | scaffolded once, **only when `--federation`** | RS256 keypair — gitignore the private one, share the public one with trusted peers |

---

## Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `HO_JWT_SECRET` | HS256 only | Shared HMAC secret. Random, scaffolded once. |
| `HO_JWT_ALGORITHM` | optional, default `HS256` | `HS256` or `RS256`. |
| `HO_JWT_PRIVATE_KEY_FILE` | RS256 only | Path to the private key (signing). |
| `HO_JWT_PUBLIC_KEY_FILE` | RS256 only | Path to the public key (verification, and what you hand to trusted peers). |
| `HO_PEER_ID` | federation only | This project's own stable identifier (uuid), auto-generated once. The actual key other peers use to look you up — never change it after registering with anyone. |
| `HO_PEER_NAME` | federation only | This project's own self-declared name, shown to other peers via its registration card. Set once, by you — never chosen by whoever registers your peer entry. |
| `HO_PEER_URL` | federation only | This project's own public **API** base URL. **Must include the API version prefix** (e.g. `/v0`) — every route, including `federation.py`'s, is mounted under it. See [federation.md](federation.md#gotcha-the-api-version-prefix). |
| `HO_FRONTEND_URL` | federation only | This project's own **frontend** base URL (no version prefix). Where `/auth/login` sends the browser when this peer is the identity source for another peer's delegated login. |
| `HO_LOCAL_AUTH` | optional, default `db` | `db` (check `half_orm_meta.identity.user.password_hash`) or `none` (disable local sign-in entirely — federation-only peer). |
