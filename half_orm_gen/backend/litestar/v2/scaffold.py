"""
Scaffold ho_api/ for a Litestar-backed halfORM project.

Files always regenerated:
  ho_api/app.py             — application entry point
  ho_api/authorization.py   — JWT middleware (reads HO_JWT_SECRET/HO_JWT_ALGORITHM from env)
  ho_api/local_auth.py      — pluggable local authentication (DB by default)
  ho_api/federation.py      — cross-peer login delegation (federation only)
  ho_api/.env.example       — documents required environment variables

Files scaffolded once (never overwritten):
  ho_api/custom/middlewares/jwt_config.py — developer hook: enrich_state()
  ho_api/custom/local_auth.py.example     — documentation-only local-auth example (e.g. LDAP)
  ho_api/custom/guards.py.example         — documentation-only custom-guard example (@tools.api_*)
  ho_api/.env                             — secret/key-file references (must be gitignored)
  ho_api/private_key.pem                  — RS256 private key (federation only, gitignored)
  ho_api/public_key.pem                   — RS256 public key (federation only — share with trusted peers)
"""

import secrets
import uuid
from pathlib import Path


def _generate_rs256_keypair() -> tuple[bytes, bytes]:
    """Generate an RSA keypair for RS256 JWT signing/verification.

    Used only for projects that register with a federation of trusted
    peers — standalone projects keep the simpler HS256 shared secret.
    See planning/identite_federee.md for the rationale (verifying a peer's
    tokens must never grant the ability to forge them, which a shared
    HMAC secret would).
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem

# ---------------------------------------------------------------------------
# ho_api/app.py  (always regenerated)
# ---------------------------------------------------------------------------

_APP_TEMPLATE = """\
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cur_dir)
par_dir = os.path.join(cur_dir, os.path.pardir)
sys.path.insert(0, par_dir)

# Load ho_api/.env if present (env vars already set take precedence)
_env_file = os.path.join(cur_dir, '.env')
if os.path.isfile(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())

# Normalize key-file paths to absolute, once, here — they're written to
# ho_api/.env relative to ho_api/ (see scaffold_api_dir), and this is the
# one place in the whole app that's guaranteed to run from ho_api/'s own
# __file__-relative cur_dir, before any other code (including installed
# half_orm_gen code, which has no reason to know this project's layout)
# reads HO_JWT_PRIVATE_KEY_FILE / HO_JWT_PUBLIC_KEY_FILE from the environment.
for _key_var in ('HO_JWT_PRIVATE_KEY_FILE', 'HO_JWT_PUBLIC_KEY_FILE'):
    _key_val = os.environ.get(_key_var)
    if _key_val and not os.path.isabs(_key_val):
        os.environ[_key_var] = os.path.join(cur_dir, _key_val)

from half_orm_gen.backend.litestar.v2.runtime import build_crud_app
from half_orm_gen.backend.ho_api.context import HalfOrmContext
from {module_name} import MODEL
{meta_import}
_ctx = HalfOrmContext(MODEL, {meta_model_expr})

# Must happen before anything else below touches _ctx.meta_model —
# federation.py and any project's own ho_api/custom/routes.py both call
# model.get_relation_class(...) for half_orm_meta tables (e.g. Peer) at
# import time, expecting the classes half_orm_meta.identity/api define
# (Peer.lookup_trusted, User.authenticate, ...) rather than a generic
# dynamically-built one — which is only true once they've been registered.
# build_crud_app also registers them (idempotent), but by then
# federation_setup below would already have run with the wrong classes.
from half_orm_gen.backend.ho_api import half_orm_meta as _half_orm_meta
_half_orm_meta.register_all(_ctx.meta_model)

from ho_api.authorization import Authorization

_middleware: list = [Authorization]
_route_handlers: list = []
{federation_setup}
try:
    from ho_api.custom.middlewares import middlewares as _extra_middleware
    _middleware = _middleware + _extra_middleware
except ImportError:
    pass

try:
    from ho_api.custom.routes import routes as _custom_routes
    _route_handlers = _route_handlers + _custom_routes
except ImportError:
    pass

try:
    from ho_api.custom.guards import guards as _custom_guards
except ImportError:
    _custom_guards = {}

application = build_crud_app(
    _ctx,
    module_name='{module_name}',
    api_version={api_version},
    middleware=_middleware,
    route_handlers=_route_handlers,
    custom_guards=_custom_guards,
)
"""

# Spliced into _APP_TEMPLATE's {federation_setup} placeholder only when
# scaffold_api_dir(federation=True) — adds ho_api/federation.py's handlers
# to _route_handlers before custom/routes.py (if any) is appended.
_FEDERATION_SETUP = """\
from ho_api.federation import make_federation_handlers
_route_handlers = _route_handlers + make_federation_handlers(_ctx.meta_model)
"""

# ---------------------------------------------------------------------------
# ho_api/federation.py  (always regenerated, only written when federation=True)
# ---------------------------------------------------------------------------

_FEDERATION_TEMPLATE = """\
\"\"\"
Cross-peer login delegation — generated by `half_orm gen api --federation`.

GET /auth/login?peer=<uuid>&return_to=<path>
  (This peer is the REQUESTER.) `peer` is the target's own HO_PEER_ID
  (stable, self-declared — never a free-text name, see planning/
  identite_federee.md section 4bis). Redirect the browser to that trusted
  peer's own /auth/login, carrying a fresh anti-CSRF `state` and a
  `redirect_uri` pointing back at this project's own /auth/callback.

GET /auth/login?redirect_uri=<url>&csrf_state=<state>
  (This peer is the IDENTITY SOURCE for someone else's login attempt on
  another peer.) Redirect the browser to THIS project's own frontend
  (HO_FRONTEND_URL) `/auth/delegate` page, carrying the same redirect_uri
  and csrf_state — the frontend shows its ordinary login form and, once
  authenticated, forwards the resulting (already RS256-signed) local
  token to redirect_uri itself. No separate signing step is needed here:
  a local login token issued while HO_JWT_ALGORITHM=RS256 is signed with
  this project's own private key — the exact key pair whose public half
  is what other peers register in their own "half_orm_meta.identity".peer
  row for this project — so it's already a valid federation proof.

POST /auth/callback  {token: <jwt>, csrf_state: <state>}  (form-encoded)
  Validate `state` (exists, not expired, single-use — deleted on read),
  verify `token`'s signature against the SPECIFIC peer that state was
  issued for (never "any trusted peer"), upsert
  "half_orm_meta.identity"."user" (origin_peer_id = that peer), mint a
  local session JWT signed with THIS peer's own private key, and redirect
  to the original return_to with that token.

  POST rather than GET: the frontend reaches this endpoint via a real
  top-level navigation (an auto-submitting hidden form, not fetch()) so the
  incoming federation token never lands in a URL query string — no access
  log line, no browser history entry, no Referer leak.

See planning/identite_federee.md section 4 for the full protocol
rationale (why browser redirect rather than server-to-server credential
relay; why state must be bound to one specific peer; why redirect_uri
must be validated against that peer's own registered URL — an
unvalidated redirect_uri would let an attacker exfiltrate a validly
signed identity token to a site they control).
\"\"\"
import datetime
import os
import secrets
import time
import uuid as _uuid
from typing import Annotated

import jwt as _jwt
from litestar import get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar.response import Redirect

_STATE_TTL_SECONDS = 600  # 10 minutes

_ALGORITHM = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
_PRIVATE_KEY_FILE = os.environ.get('HO_JWT_PRIVATE_KEY_FILE')
_THIS_PEER_ID = os.environ.get('HO_PEER_ID', '')
_THIS_PEER_URL = os.environ.get('HO_PEER_URL', '')
_THIS_FRONTEND_URL = os.environ.get('HO_FRONTEND_URL', '')

if _ALGORITHM != 'RS256' or not _PRIVATE_KEY_FILE:
    raise RuntimeError(
        'Federation requires RS256 (HO_JWT_ALGORITHM=RS256) and '
        'HO_JWT_PRIVATE_KEY_FILE to be set in ho_api/.env — regenerate '
        'with `half_orm gen api --litestar --federation`.'
    )
if not _THIS_PEER_ID:
    raise RuntimeError(
        'HO_PEER_ID environment variable is not set — regenerate with '
        '`half_orm gen api --litestar --federation`.'
    )
if not _THIS_PEER_URL:
    raise RuntimeError(
        'HO_PEER_URL environment variable is not set — it must be this '
        "project's own public base URL, used as the redirect_uri target "
        'peers send validated tokens back to.'
    )
if not _THIS_FRONTEND_URL:
    raise RuntimeError(
        'HO_FRONTEND_URL environment variable is not set — it must be '
        "this project's own frontend base URL, used to serve the login "
        'page when this peer is the identity source for another peer.'
    )

_cur_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_cur_dir, _PRIVATE_KEY_FILE)) as _f:
    _PRIVATE_KEY = _f.read()


def _sign_local_token(user_id: str, roles: list[str]) -> str:
    payload = {'sub': user_id, 'roles': roles, 'iat': int(time.time())}
    return _jwt.encode(payload, _PRIVATE_KEY, algorithm='RS256')


def make_federation_handlers(model) -> list:
    Peer       = model.get_relation_class('"half_orm_meta.identity".peer')
    LoginState = model.get_relation_class('"half_orm_meta.identity".login_state')
    User       = model.get_relation_class('"half_orm_meta.identity"."user"')
    UserRole   = model.get_relation_class('"half_orm_meta.api".user_role')

    # A single /auth/login handles both directions of the protocol — which
    # one applies is determined by which query params are present, not by
    # a separate path, since "this project's own /auth/login" is the one
    # fixed, well-known URL every peer redirects to (see planning/
    # identite_federee.md section 4: "chaque silo expose déjà nativement un
    # /auth/login").
    @get('/auth/login')
    async def auth_login(
        peer: str | None = None,
        return_to: str = '/',
        redirect_uri: str | None = None,
        csrf_state: str | None = None,
    ) -> Redirect:
        # Case 1 — another peer is delegating a login attempt to THIS
        # project: send the browser to our own frontend's login form.
        if redirect_uri and csrf_state:
            target = (
                f'{_THIS_FRONTEND_URL}/auth/delegate'
                f'?redirect_uri={redirect_uri}&csrf_state={csrf_state}'
            )
            return Redirect(path=target)

        # Case 2 — this project is initiating a delegated login to `peer`.
        # `peer` is the target's own HO_PEER_ID (uuid), not a free-text name —
        # see planning/identite_federee.md section 4bis: the free-text `name`
        # is cosmetic/local only, never a reliable cross-peer lookup key.
        if not peer:
            raise HTTPException(status_code=400, detail='Missing peer, or redirect_uri+csrf_state')
        try:
            peer_uid = _uuid.UUID(peer)
        except ValueError:
            raise HTTPException(status_code=400, detail='peer must be a uuid (HO_PEER_ID), not a name')
        peer_row = await Peer.lookup_trusted(peer_uid)
        if not peer_row:
            raise HTTPException(status_code=404, detail=f'Unknown or untrusted peer: {peer}')
        state_value = secrets.token_urlsafe(32)
        await LoginState.create(state_value, peer_row['id'], return_to)
        callback_uri = f'{_THIS_PEER_URL}/auth/callback'
        target = f"{peer_row['url']}/auth/login?redirect_uri={callback_uri}&csrf_state={state_value}"
        return Redirect(path=target)

    # NB: the field can't be named `state` — Litestar reserves that name for
    # its own injected `litestar.datastructures.State` app-state object.
    # POST + form-encoded body (not GET query params) — see the module
    # docstring: keeps the federation token out of the URL entirely.
    @post('/auth/callback')
    async def federation_callback(
        data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Redirect:
        token      = data.get('token')
        csrf_state = data.get('csrf_state')
        if not token or not csrf_state:
            raise HTTPException(status_code=400, detail='token and csrf_state required')
        state_row = await LoginState.consume(csrf_state)
        if not state_row:
            raise HTTPException(status_code=400, detail='Unknown or already-used login state')

        age = (
            datetime.datetime.now(datetime.timezone.utc) - state_row['created_at']
        ).total_seconds()
        if age > _STATE_TTL_SECONDS:
            raise HTTPException(status_code=400, detail='Expired login state')

        peer_row = await Peer.lookup(state_row['peer_id'])
        if not peer_row or not peer_row['trusted'] or not peer_row['jwt_public_key']:
            raise HTTPException(status_code=403, detail='Peer is not (or no longer) trusted')
        public_key = peer_row['jwt_public_key']

        # Verify against THIS SPECIFIC peer's key — not "any trusted peer" —
        # otherwise a different (still trusted) peer could substitute its
        # own token for this callback.
        try:
            payload = _jwt.decode(token, public_key, algorithms=['RS256'])
        except _jwt.PyJWTError:
            raise HTTPException(status_code=401, detail='Invalid token signature')

        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(status_code=400, detail="Token missing 'sub' claim")
        uid = _uuid.UUID(user_id)
        now = datetime.datetime.now(datetime.timezone.utc)

        await User.upsert_from_federation(
            uid, state_row['peer_id'], payload.get('name'), payload.get('email'), now,
        )

        local_token = _sign_local_token(user_id, await UserRole.roles_for(user_id))
        return_to = state_row['return_to'] or '/'
        # Fragment, not query string: return_to is a static SPA route with no
        # backend of its own to read a POST body from, so the token can't
        # travel the same way the incoming one did above. A URL fragment is
        # never sent to the server by the browser (stripped before the HTTP
        # request line is built) — no access log line, no Referer leak —
        # while still being readable client-side via window.location.hash
        # (see the frontend's auth-callback page).
        return Redirect(path=f'{return_to}#token={local_token}')

    return [auth_login, federation_callback]
"""

# ---------------------------------------------------------------------------
# ho_api/authorization.py  (always regenerated)
# ---------------------------------------------------------------------------

_AUTHORIZATION_TEMPLATE = """\
\"\"\"
JWT authorization middleware — generated by half_orm gen api.

On each request:
  1. Decode the Bearer JWT using HO_JWT_ALGORITHM (HS256: HO_JWT_SECRET;
     RS256: the public key at HO_JWT_PUBLIC_KEY_FILE).
  2. Set request.state.user             = payload['sub']
  3. Set request.state.authorized_roles = payload.get('roles', ['connected'])
     (route handlers expand the hierarchy via _expand_roles at call time)
  4. Call enrich_state(payload, state) if jwt_config.py provides it.

Fails at startup with a clear error if the configured key/secret is not set.
RS256 is only needed for projects registered in a federation of trusted
peers (see ho_api/federation.py and planning/identite_federee.md) — a
standalone project keeps the simpler HS256 shared secret.

To add extra claims to request.state, create:
  ho_api/custom/middlewares/jwt_config.py
with:
  async def enrich_state(payload: dict, state: dict) -> None: ...
\"\"\"
import os
import uuid as _uuid

import jwt as _jwt
from litestar.types import ASGIApp, Receive, Scope, Send

_ALGORITHM = os.environ.get('HO_JWT_ALGORITHM', 'HS256')

if _ALGORITHM == 'RS256':
    _KEY_FILE = os.environ.get('HO_JWT_PUBLIC_KEY_FILE')
    if not _KEY_FILE:
        raise RuntimeError(
            'HO_JWT_PUBLIC_KEY_FILE environment variable is not set.\\n'
            'Add it to ho_api/.env (see .env.example).'
        )
    _cur_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_cur_dir, _KEY_FILE)) as _f:
        _VERIFY_KEY = _f.read()
else:
    _VERIFY_KEY = os.environ.get('HO_JWT_SECRET')
    if not _VERIFY_KEY:
        raise RuntimeError(
            'HO_JWT_SECRET environment variable is not set.\\n'
            'Add it to ho_api/.env (see .env.example) and make sure it is '
            'exported before starting the server.'
        )

try:
    from ho_api.custom.middlewares.jwt_config import enrich_state as _enrich_state
except ImportError:
    async def _enrich_state(payload: dict, state: dict) -> None:  # type: ignore[misc]
        pass


class Authorization:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            from litestar.connection import Request
            token = (
                Request(scope)
                .headers.get('Authorization', '')
                .removeprefix('Bearer ')
                .strip()
            )
            state: dict = scope.setdefault('state', {})
            if token:
                try:
                    payload = _jwt.decode(token, _VERIFY_KEY, algorithms=[_ALGORITHM])
                    user_id = payload.get('sub')
                    if user_id:
                        try:
                            state['user'] = _uuid.UUID(user_id)
                        except (ValueError, AttributeError):
                            state['user'] = user_id
                    # Store explicit roles — route handlers expand the hierarchy
                    state['authorized_roles'] = payload.get('roles', ['connected'])
                    await _enrich_state(payload, state)
                except _jwt.PyJWTError:
                    state['authorized_roles'] = ['anonymous']
            else:
                state['authorized_roles'] = ['anonymous']
        await self.app(scope, receive, send)
"""

# ---------------------------------------------------------------------------
# ho_api/.env.example  (always regenerated)
# ---------------------------------------------------------------------------

_ENV_EXAMPLE = """\
# Required — JWT signing secret. Generate with: python -c "import secrets; print(secrets.token_hex(32))"
HO_JWT_SECRET=

# Optional — JWT algorithm (default: HS256)
# HO_JWT_ALGORITHM=HS256

# --- Federation (only if this project registers with trusted peers) ---
# HO_JWT_ALGORITHM=RS256
# HO_JWT_PRIVATE_KEY_FILE=private_key.pem
# HO_JWT_PUBLIC_KEY_FILE=public_key.pem
# HO_PEER_ID is auto-generated once (do not change — other peers register
# you by this value, not by name).
# HO_PEER_ID=<uuid, generated automatically>
# HO_PEER_NAME is this project's own self-declared name — set once, shown
# to other peers via the registration card (/ho_admin/peer/self).
# HO_PEER_NAME=my-project
# HO_PEER_URL must include the API version prefix (e.g. /v0) if any — every
# route, including federation.py's, is mounted under it.
# HO_PEER_URL=https://this-project.example.com/v0     # this project's own public API base URL
# HO_FRONTEND_URL=https://this-project.example.com   # this project's own frontend base URL (no prefix)

# Optional — local authentication method (default: db)
# HO_LOCAL_AUTH=db     # check "half_orm_meta.identity"."user".password_hash
# HO_LOCAL_AUTH=none   # disable local sign-in entirely (federation-only peer)
"""

# ---------------------------------------------------------------------------
# ho_api/local_auth.py  (always regenerated)
# ---------------------------------------------------------------------------

_LOCAL_AUTH_TEMPLATE = """\
\"\"\"
Pluggable local authentication — generated by half_orm gen api.

authenticate(model, email, password) -> the person's UUID (str), or None.

Default (HO_LOCAL_AUTH=db, or unset): checks
"half_orm_meta.identity"."user".password_hash (bcrypt).

HO_LOCAL_AUTH=none disables local sign-in entirely — for a federation-only
peer that only accepts sign-ins delegated from trusted peers (see
ho_api/federation.py and planning/identite_federee.md).

To authenticate a different way (LDAP, an external directory, ...),
implement authenticate(model, email, password) in
ho_api/custom/local_auth.py (see custom/local_auth.py.example) — it takes
over from the default DB check whenever that module is present.
\"\"\"
import os

HO_LOCAL_AUTH = os.environ.get('HO_LOCAL_AUTH', 'db')

try:
    from ho_api.custom.local_auth import authenticate as _custom_authenticate
except ImportError:
    _custom_authenticate = None


async def authenticate(model, email: str, password: str) -> str | None:
    \"\"\"Return the authenticated person's UUID (as str), or None.\"\"\"
    if HO_LOCAL_AUTH == 'none':
        return None
    if _custom_authenticate is not None:
        return await _custom_authenticate(model, email, password)
    User = model.get_relation_class('"half_orm_meta.identity"."user"')
    return await User.authenticate(email, password)
"""

# ---------------------------------------------------------------------------
# ho_api/custom/local_auth.py.example  (scaffolded once, documentation only —
# never imported; copy to local_auth.py to actually enable it)
# ---------------------------------------------------------------------------

_CUSTOM_LOCAL_AUTH_EXAMPLE = """\
\"\"\"
Example custom local authenticator — e.g. for LDAP.

This file is NOT imported by default (note the .example suffix). Copy it
to ho_api/custom/local_auth.py to replace the default DB-based check in
ho_api/local_auth.py with your own implementation, matching this exact
signature.
\"\"\"


async def authenticate(model, email: str, password: str) -> str | None:
    \"\"\"Return the authenticated person's UUID (as str), or None.

    Example (LDAP, pseudocode):
        import ldap3
        conn = ldap3.Connection(LDAP_SERVER, user=f'uid={email},...', password=password)
        if not conn.bind():
            return None
        return _uuid_for_ldap_entry(conn)
    \"\"\"
    raise NotImplementedError
"""

# ---------------------------------------------------------------------------
# ho_api/custom/guards.py.example  (scaffolded once, documentation only —
# never imported; copy to guards.py to actually define custom guards)
# ---------------------------------------------------------------------------

_CUSTOM_GUARDS_EXAMPLE = """\
\"\"\"
Example custom guards for @tools.api_* routes (half_orm_gen.tools).

This file is NOT imported by default (note the .example suffix). Copy it
to ho_api/custom/guards.py to define `guards`, a dict mapping the name
strings used in a route's `guards=[...]` to a real litestar Guard callable
— `async def guard(connection, route_handler) -> None`, raising to deny.

Any name not found here falls back to a simple check: the caller must have
that name among their roles (expanded through the role hierarchy) — enough
for "requires role X" without writing any code. Define a guard here only
when the check can't be expressed as local role membership — typically
because it depends on something outside this project's own database, e.g.
querying another API to check whether the connected user belongs to a
group defined elsewhere.
\"\"\"


async def in_external_group(connection, route_handler) -> None:
    \"\"\"Example: authorize via a group membership defined in another system.

    from litestar.exceptions import NotAuthorizedException
    import httpx

    user_id = connection.state.user_id
    async with httpx.AsyncClient() as client:
        resp = await client.get(f'https://groups.example.com/members/{user_id}')
    if resp.status_code != 200 or 'editors' not in resp.json().get('groups', []):
        raise NotAuthorizedException('Not a member of the editors group')
    \"\"\"
    raise NotImplementedError


guards = {
    # 'in_external_group': in_external_group,
}
"""

# ---------------------------------------------------------------------------
# ho_api/custom/middlewares/jwt_config.py  (scaffolded once)
# ---------------------------------------------------------------------------

_JWT_CONFIG_TEMPLATE = """\
\"\"\"
Developer hook for the JWT authorization middleware.
Scaffolded once by `half_orm gen api` — never overwritten.

Implement enrich_state to add extra JWT claims to request.state
for use in application-level route handlers.
\"\"\"


async def enrich_state(payload: dict, state: dict) -> None:
    \"\"\"Add extra decoded claims to request.state.

    Examples:
        state['tenant_id'] = payload.get('tenant_id')
        state['email']     = payload.get('email')
    \"\"\"
"""


def scaffold_api_dir(
    api_dir: Path,
    module_name: str = '',
    meta_module_name: str | None = None,
    api_version: int | None = None,
    federation: bool = False,
) -> None:
    """Write ho_api/app.py and authorization.py. Always regenerated.

    meta_module_name: top-level package exposing MODEL for the database that
    owns "half_orm_meta.api"/".identity", when it's a separate database from
    the business one (module_name). None means they're the same database.

    federation: when True, scaffold an RS256 keypair instead of the default
    HS256 shared secret — needed only for projects that will register with
    a federation of trusted peers (see ho_api/federation.py,
    planning/identite_federee.md). Standalone projects keep the simpler
    HS256 scheme.
    """
    api_dir.mkdir(parents=True, exist_ok=True)
    version_str = str(api_version) if api_version is not None else 'None'

    if meta_module_name and meta_module_name != module_name:
        meta_import = f'from {meta_module_name} import MODEL as META_MODEL'
        meta_model_expr = 'META_MODEL'
    else:
        meta_import = ''
        meta_model_expr = 'None'

    # app.py — always regenerated
    app_py = api_dir / 'app.py'
    content = (
        _APP_TEMPLATE
        .replace('{module_name}', module_name)
        .replace('{meta_import}', meta_import)
        .replace('{meta_model_expr}', meta_model_expr)
        .replace('{api_version}', version_str)
        .replace('{federation_setup}', _FEDERATION_SETUP if federation else '')
    )
    app_py.write_text(content, encoding='utf-8')
    print(f'  updated  {app_py}')

    # authorization.py — always regenerated
    auth_py = api_dir / 'authorization.py'
    auth_py.write_text(_AUTHORIZATION_TEMPLATE, encoding='utf-8')
    print(f'  updated  {auth_py}')

    # local_auth.py — always regenerated
    local_auth_py = api_dir / 'local_auth.py'
    local_auth_py.write_text(_LOCAL_AUTH_TEMPLATE, encoding='utf-8')
    print(f'  updated  {local_auth_py}')

    # federation.py — always regenerated, only written when federation=True
    federation_py = api_dir / 'federation.py'
    if federation:
        federation_py.write_text(_FEDERATION_TEMPLATE, encoding='utf-8')
        print(f'  updated  {federation_py}')

    # .env.example — always regenerated
    env_example = api_dir / '.env.example'
    env_example.write_text(_ENV_EXAMPLE, encoding='utf-8')
    print(f'  updated  {env_example}')

    # .env — scaffolded once, with either an HS256 secret or an RS256 keypair
    env_file = api_dir / '.env'
    if not env_file.exists():
        if federation:
            private_pem, public_pem = _generate_rs256_keypair()
            private_key_file = api_dir / 'private_key.pem'
            public_key_file = api_dir / 'public_key.pem'
            private_key_file.write_bytes(private_pem)
            public_key_file.write_bytes(public_pem)
            peer_id = str(uuid.uuid4())
            env_file.write_text(
                'HO_JWT_ALGORITHM=RS256\n'
                'HO_JWT_PRIVATE_KEY_FILE=private_key.pem\n'
                'HO_JWT_PUBLIC_KEY_FILE=public_key.pem\n'
                '# Auto-generated, stable — other peers register you by this value, not by\n'
                '# name. Do not change once you have registered with any peer.\n'
                f'HO_PEER_ID={peer_id}\n'
                '# Required — the name this project gives itself, shown to other peers via\n'
                '# its registration card (/ho_admin/peer/self).\n'
                'HO_PEER_NAME=\n'
                '# Required — this project\'s own public API base URL (peers redirect back here).\n'
                '# Include the API version prefix if any (e.g. /v0) — every route, including\n'
                '# federation.py\'s, is mounted under it.\n'
                'HO_PEER_URL=\n'
                '# Required — this project\'s own frontend base URL (serves the login form when\n'
                '# this peer is the identity source for another peer\'s delegated login)\n'
                'HO_FRONTEND_URL=\n',
                encoding='utf-8',
            )
            print(f'  created  {private_key_file}  (gitignore this file!)')
            print(f'  created  {public_key_file}  (share this with trusted peers)')
            print(f'  NOTE: set HO_PEER_NAME, HO_PEER_URL and HO_FRONTEND_URL in {env_file}')
        else:
            secret = secrets.token_hex(32)
            env_file.write_text(f'HO_JWT_SECRET={secret}\n', encoding='utf-8')
        print(f'  created  {env_file}  (gitignore this file!)')

    # jwt_config.py — scaffolded once
    jwt_config = api_dir / 'custom' / 'middlewares' / 'jwt_config.py'
    if not jwt_config.exists():
        jwt_config.parent.mkdir(parents=True, exist_ok=True)
        jwt_config.write_text(_JWT_CONFIG_TEMPLATE, encoding='utf-8')
        # ensure __init__.py files exist
        for init in (
            api_dir / 'custom' / '__init__.py',
            api_dir / 'custom' / 'middlewares' / '__init__.py',
        ):
            if not init.exists():
                init.write_text('', encoding='utf-8')
        print(f'  created  {jwt_config}')

    # custom/local_auth.py.example — scaffolded once, documentation only
    # (the .example suffix means it's never imported by local_auth.py;
    # copy it to custom/local_auth.py to actually plug in e.g. LDAP)
    local_auth_example = api_dir / 'custom' / 'local_auth.py.example'
    if not local_auth_example.exists():
        local_auth_example.parent.mkdir(parents=True, exist_ok=True)
        local_auth_example.write_text(_CUSTOM_LOCAL_AUTH_EXAMPLE, encoding='utf-8')
        init = api_dir / 'custom' / '__init__.py'
        if not init.exists():
            init.write_text('', encoding='utf-8')
        print(f'  created  {local_auth_example}')

    # custom/guards.py.example — scaffolded once, documentation only
    # (the .example suffix means it's never imported; copy it to
    # custom/guards.py to define guards for @tools.api_* routes)
    guards_example = api_dir / 'custom' / 'guards.py.example'
    if not guards_example.exists():
        guards_example.parent.mkdir(parents=True, exist_ok=True)
        guards_example.write_text(_CUSTOM_GUARDS_EXAMPLE, encoding='utf-8')
        init = api_dir / 'custom' / '__init__.py'
        if not init.exists():
            init.write_text('', encoding='utf-8')
        print(f'  created  {guards_example}')
