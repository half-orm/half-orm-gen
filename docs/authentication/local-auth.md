# Local authentication

> Back to overview: [overview.md](overview.md)  
> Federated (cross-peer) sign-in: [federation.md](federation.md)  
> JWT middleware / roles / CRUD_ACCESS: [../backend/authorization.md](../backend/authorization.md)

---

## What's generated, and what isn't

`half_orm gen api` never generates a login or signup route. Identity
requirements (what counts as a valid credential, whether email must be
unique, whether signup is even allowed) are entirely project-specific, so
the framework only scaffolds:

- `ho_api/custom/routes.py` — an empty (or example) file, **yours to write**.
- `ho_api/local_auth.py` — generated, pluggable password check, described below.
- `ho_api/authorization.py` — generated, decodes whatever token your login
  route hands back.

The one contract your login/signup handlers must honor: return a JSON body
shaped `{"token": "<jwt>"}`. The frontend's `AuthService.loginWithEmail` /
`signupUser` (see [auth-service-reference.md](../frontend/auth-service-reference.md))
expect exactly that.

```python
# ho_api/custom/routes.py
@post('/auth/login')
async def login(data: dict) -> dict:
    user_id = await authenticate(MODEL, data['email'], data['password'])
    if not user_id:
        raise HTTPException(status_code=401, detail='Invalid email or password')
    roles = [...]  # look up in half_orm_meta.api.user_role
    return {'token': _sign(user_id, roles)}

routes = [login, signup, ...]
```

`_sign` is also yours to write — see [JWT signing](#jwt-signing) below for
what it needs to do depending on `HO_JWT_ALGORITHM`.

---

## The identity table

Regardless of local vs federated, every person half-orm-gen knows about
(locally authenticated or delegated in from a peer) is a row in:

```sql
CREATE TABLE "half_orm_meta.identity"."user" (
  id             uuid PRIMARY KEY,
  origin_peer_id uuid REFERENCES "half_orm_meta.identity".peer(id) ON DELETE SET NULL,
  name           text,
  email          text,
  password_hash  text,
  first_seen_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at   timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

This table (and the rest of the `half_orm_meta.identity` schema) is created
by every project, federation or not — cheap and harmless if unused, since
`half_orm_meta`-prefixed schemas are automatically excluded from generic
CRUD route generation (halfORM's own `model.classes()` skips them).

- `id` is **not** server-generated — it's whatever ends up in a JWT's `sub`
  claim, so it must stay stable across a person's whole lifetime, including
  if they're later delegated in from another peer.
- `origin_peer_id` is `NULL` for a locally-registered identity, or the peer
  that first vouched for it (see [federation.md](federation.md)).
- `password_hash` is only ever set for identities that authenticate
  **locally on this project** (`HO_LOCAL_AUTH=db`). An identity whose
  origin is another peer authenticates via that peer's signed token
  instead — it has no local password, by design (attempting a direct
  email/password login for such an account will correctly fail).

If your project already has its own user table, you don't have to migrate
to this one — wire your own login route against whatever table you already
have. `half_orm_meta.identity.user` only needs to be populated for
identities you want to expose to (or accept from) other peers.

---

## `local_auth.py` — pluggable password check

Generated, always regenerated, at `ho_api/local_auth.py`:

```python
async def authenticate(model, email: str, password: str) -> str | None:
    """Return the authenticated person's UUID (as str), or None."""
```

Behavior depends on `HO_LOCAL_AUTH`:

| `HO_LOCAL_AUTH` | Behavior |
|---|---|
| `db` (default, or unset) | Looks up `half_orm_meta.identity.user` by email, checks `password_hash` with bcrypt. |
| `none` | Always returns `None` — disables local sign-in entirely. Use this for a peer that *only* accepts federated sign-ins (see [federation.md](federation.md)); such a peer never stores a `password_hash` for anyone. |

### Custom authentication (LDAP, an external directory, ...)

`local_auth.py` looks for `ho_api.custom.local_auth.authenticate` first,
falling back to the DB check only if that module doesn't exist:

```python
try:
    from ho_api.custom.local_auth import authenticate as _custom_authenticate
except ImportError:
    _custom_authenticate = None

async def authenticate(model, email: str, password: str) -> str | None:
    if HO_LOCAL_AUTH == 'none':
        return None
    if _custom_authenticate is not None:
        return await _custom_authenticate(model, email, password)
    return await _authenticate_db(model, email, password)
```

A template lives at `ho_api/custom/local_auth.py.example` (scaffolded once,
**never imported by default** — note the `.example` suffix). Copy it to
`ho_api/custom/local_auth.py` and implement `authenticate` against your own
directory to replace the DB check:

```python
async def authenticate(model, email: str, password: str) -> str | None:
    import ldap3
    conn = ldap3.Connection(LDAP_SERVER, user=f'uid={email},...', password=password)
    if not conn.bind():
        return None
    return _uuid_for_ldap_entry(conn)
```

This is orthogonal to federation: each peer picks its own local
authentication method independently. A peer using LDAP locally can still
delegate sign-in to (or accept delegation from) a peer that uses DB
passwords — the cross-peer protocol only ever exchanges a signed identity
token, never credentials or the authentication method used to obtain them.

---

## JWT signing

### HS256 (default)

One shared secret (`HO_JWT_SECRET`), scaffolded once as a random 32-byte
hex string. Anyone who has it can both sign and verify — fine for a single
project, unusable for federation (a peer able to verify another peer's
tokens would then also be able to forge them).

```python
jwt.encode({'sub': user_id, 'roles': roles}, secret, algorithm='HS256')
```

### RS256 (federation only, opt-in)

`half_orm gen api --litestar --federation` generates an RSA-2048 keypair
instead (`private_key.pem` / `public_key.pem`) and sets
`HO_JWT_ALGORITHM=RS256` in `.env`. Signing uses the private key; verifying
(both this project's own `authorization.py` middleware, and any other peer
checking a token this project issued) uses the public key. See
[federation.md](federation.md) for how the public key gets shared with
trusted peers.

```python
def _sign(user_id: str, roles: list[str]) -> str:
    algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
    if algorithm == 'RS256':
        with open(os.environ['HO_JWT_PRIVATE_KEY_FILE']) as f:
            key = f.read()
    else:
        key = os.environ['HO_JWT_SECRET']
    return jwt.encode({'sub': user_id, 'roles': roles}, key, algorithm=algorithm)
```

**Important**: a local login token issued while `HO_JWT_ALGORITHM=RS256` is
already a valid federation proof — it's signed with this project's own
private key, the exact keypair whose public half other peers register.
This is why the federated delegation flow (see
[federation-protocol.md](../internals/federation-protocol.md#the-delegation-protocol)) doesn't need a
separate signing step: it just forwards the ordinary local login token.

### `authorization.py` — verification side

Generated, always regenerated, branches on the same `HO_JWT_ALGORITHM`:

```python
_ALGORITHM = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
if _ALGORITHM == 'RS256':
    with open(os.environ['HO_JWT_PUBLIC_KEY_FILE']) as f:
        _VERIFY_KEY = f.read()
else:
    _VERIFY_KEY = os.environ['HO_JWT_SECRET']

payload = jwt.decode(token, _VERIFY_KEY, algorithms=[_ALGORITHM])
```

Full details on what happens with the decoded payload (roles, hierarchy
expansion, the `enrich_state` hook) are in
[authorization.md](../backend/authorization.md#generated-jwt-middleware).
