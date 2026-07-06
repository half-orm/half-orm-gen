#!/usr/bin/env bash
# Demo script: pages (wiki) example end-to-end — a SEPARATE domain from
# blog_demo, used to prove out identity federation (planning/identite_federee.md).
# Registered as a trusted peer of blog_demo (and vice versa) via `make demo-federate`,
# which runs after both demos have been (re)generated.
#
# Usage: bash demo_pages.sh
#        bash demo_pages.sh --cleanup   (drop DB + remove project dir only)

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
FIXTURES_DIR="$SCRIPT_DIR/../../../fixtures"
source "$SCRIPT_DIR/common.sh"

PROJECT="pages_demo"
DEMOS_DIR="$SCRIPT_DIR/demos"
GIT_BARE="/tmp/${PROJECT}.git"
export HALFORM_CONF_DIR="$DEMOS_DIR/.config"

# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------
cleanup() {
    echo -e "${YELLOW}=== CLEANUP ===${NC}"
    cd "$SCRIPT_DIR"
    rm -rf "$DEMOS_DIR/$PROJECT" "$GIT_BARE"
    set +e
    dropdb -h localhost -U "$TEST_DB_USER" "$PROJECT" 2>/dev/null
    set -e
    echo -e "${GREEN}✓ Cleaned up${NC}"
}

if [[ "${1:-}" == "--cleanup" ]]; then
    cleanup
    exit 0
fi

cleanup

# ---------------------------------------------------------------------------
# 1. DB user + git bare repo
# ---------------------------------------------------------------------------
setup_test_db_user
rm -rf "$GIT_BARE"
git init --bare "$GIT_BARE"

# ---------------------------------------------------------------------------
# 2. half-orm-dev project init
# ---------------------------------------------------------------------------
mkdir -p "$DEMOS_DIR"
cd "$DEMOS_DIR"
echo -e "${GREEN}=== INIT PROJECT ===${NC}"
half_orm dev init "$PROJECT" \
    --git-origin "$GIT_BARE" \
    --user "$TEST_DB_USER" \
    --password "$TEST_DB_PASSWORD"

cd "$PROJECT"

# ---------------------------------------------------------------------------
# 3. First release
# ---------------------------------------------------------------------------
git checkout ho-prod
half_orm dev release create minor   # ho-release/0.1.0

# ---------------------------------------------------------------------------
# 4. Patch 1: wiki schema — no FK to half_orm_meta.identity yet, that schema
#    doesn't exist until `half_orm gen api --federation` runs (step 6).
# ---------------------------------------------------------------------------
half_orm dev patch create 1-wiki-schema

cat > "Patches/1-wiki-schema/01_wiki.sql" << 'SQL'
CREATE SCHEMA wiki;

CREATE TABLE wiki.page (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT NOT NULL,
    author_id UUID
);
SQL

echo -e "${GREEN}=== APPLY PATCH 1 ===${NC}"
half_orm dev patch apply

git add .
git commit -m "Add wiki schema" --no-verify
half_orm dev patch merge
half_orm dev release promote prod

# ---------------------------------------------------------------------------
# 5. Generate gen API — with federation (RS256 keypair, half_orm_meta.identity
#    schema, ho_api/federation.py). Every rebuild gets a fresh keypair; peer
#    trust (public keys) is re-registered by `make demo-federate` afterwards.
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE gen API ===${NC}"
half_orm gen api --litestar --federation
# scaffold_api_dir already writes an empty `HO_PEER_URL=` placeholder line —
# replace it (sed) rather than appending a second one: the .env loader in
# app.py uses os.environ.setdefault() per line, so the first (empty) HO_PEER_URL
# would otherwise silently win over a second, appended one. Must include the
# API version prefix (/v0) — federation.py's routes are mounted under it
# like every other route (`gen api` defaults to api_version 0) — otherwise
# the cross-peer redirect 404s.
sed -i 's|^HO_PEER_URL=$|HO_PEER_URL=http://localhost:8001/v0|' ho_api/.env
echo -e "${GREEN}✓ Set HO_PEER_URL for federation${NC}"

# HO_PEER_NAME is this project's own self-declared name — see demo_blog.sh
# for the same convention (planning/identite_federee.md section 4bis).
sed -i 's|^HO_PEER_NAME=$|HO_PEER_NAME=pages_demo|' ho_api/.env
echo -e "${GREEN}✓ Set HO_PEER_NAME for federation${NC}"

# Pin a fixed, dev-only keypair + HO_PEER_ID across rebuilds — otherwise a
# full `make demo-pages` rebuild mints a fresh RSA keypair every time
# (cleanup() deletes the whole project dir), invalidating every session
# token already in a browser tab and forcing a re-login on every rebuild.
# See demo_blog.sh for the same fix. Never do this for a real deployment.
cp "$FIXTURES_DIR/pages_demo_private_key.pem" ho_api/private_key.pem
cp "$FIXTURES_DIR/pages_demo_public_key.pem" ho_api/public_key.pem
sed -i 's|^HO_PEER_ID=.*$|HO_PEER_ID=22222222-2222-2222-2222-222222222222|' ho_api/.env
echo -e "${GREEN}✓ Pinned dev keypair + HO_PEER_ID (stable across rebuilds)${NC}"

# HO_FRONTEND_URL is where /auth/login sends the browser when THIS peer is
# the identity source for someone else's delegated login. Angular (port
# 4300 here) is the frontend used as the federation entry point — see
# demo_blog.sh for the same convention.
sed -i 's|^HO_FRONTEND_URL=$|HO_FRONTEND_URL=http://localhost:4300|' ho_api/.env
echo -e "${GREEN}✓ Set HO_FRONTEND_URL for federation${NC}"

# ---------------------------------------------------------------------------
# 6. Patch 2: add the FK now that half_orm_meta.identity."user" exists —
#    real referential integrity, not just a logically-linked UUID. Must run
#    BEFORE `half_orm gen frontend` below, which introspects real FK
#    constraints to detect author_id as a foreign key (combobox, link, etc.).
#    A new patch requires being on a ho-release/X.Y.Z branch, not ho-prod
#    (where `release promote prod` above left us) — create one first. It
#    also requires a clean working tree — commit the files `gen api`
#    wrote (app.py, federation.py, keys, .env) first; the original blog_demo
#    script never needed to since it never created a second patch afterwards.
# ---------------------------------------------------------------------------
git checkout ho-prod
half_orm dev release create patch   # ho-release/0.1.1

git add .
git commit -m "Generate ho_api (federation)" --no-verify
git push origin ho-release/0.1.1

half_orm dev patch create 2-wiki-author-fk

cat > "Patches/2-wiki-author-fk/01_fk.sql" << 'SQL'
ALTER TABLE wiki.page
    ADD CONSTRAINT fk_page_author
    FOREIGN KEY (author_id) REFERENCES "half_orm_meta.identity"."user"(id);
SQL

echo -e "${GREEN}=== APPLY PATCH 2 ===${NC}"
half_orm dev patch apply

git add .
git commit -m "Add FK: wiki.page.author_id -> half_orm_meta.identity.user" --no-verify
half_orm dev patch merge
half_orm dev release promote prod

# ---------------------------------------------------------------------------
# 7. Generate frontends — after the FK above, so author_id is correctly
#    detected as a foreign key (fk_deps) into half_orm_meta.identity."user".
# ---------------------------------------------------------------------------
half_orm gen frontend --angular
half_orm gen frontend --svelte

# half_orm-gen always generates dev servers pointed at port 8000 (the
# generic default) — pages_demo's API runs on 8001 so it can coexist with
# blog_demo (port 8000). Patch the generated proxy/dev-server config, not
# the generator itself (this is demo-only infra, not a generic feature).
sed -i 's|"target": "http://localhost:8000"|"target": "http://localhost:8001"|' \
    ho_frontend/angular/proxy.conf.json
sed -i 's|"start": "ng serve"|"start": "ng serve --port 4300"|' \
    ho_frontend/angular/package.json
sed -i "s|target: 'http://localhost:8000'|target: 'http://localhost:8001'|" \
    ho_frontend/svelte/vite.config.ts
sed -i 's|"dev": "vite dev"|"dev": "vite dev --port 5300"|' \
    ho_frontend/svelte/package.json
sed -i 's|VITE_WS_BASE=http://localhost:8000|VITE_WS_BASE=http://localhost:8001|' \
    ho_frontend/svelte/.env.local
echo -e "${GREEN}✓ Patched frontend dev-server ports (Angular 4300, Svelte 5300 → API 8001)${NC}"

# ---------------------------------------------------------------------------
# 8. Dynamic role: author on wiki.page (same pattern as blog_demo's post_author)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== DYNAMIC ROLE: author ===${NC}"

python3 - << 'PYEOF'
import re, pathlib

path = pathlib.Path('pages_demo/wiki/page.py')
src  = path.read_text()

imports = """\
from half_orm_gen.tools import ho_api_role
"""

method = """\

    @ho_api_role('page_author')
    def _is_author(self, request, rows: list) -> set:
        user = request.state.user
        return {row['id'] for row in rows if row['author_id'] == user}
"""

src = re.sub(
    r'(#>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + imports + '\n',
    src, count=1
)
src = re.sub(
    r'(        #>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + method,
    src, count=1
)
path.write_text(src)
print('  patched pages_demo/wiki/page.py')
PYEOF

echo -e "${GREEN}✓ Dynamic role written${NC}"

# ---------------------------------------------------------------------------
# 9. Real auth routes (not yes-auth like blog_demo) — exercises the actual
#    generated local_auth.py (DB password check against
#    half_orm_meta.identity."user".password_hash), rather than bypassing it.
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== AUTH ROUTES (real local auth) ===${NC}"

cat > ho_api/custom/routes.py << 'PYEOF'
"""
Real local-auth routes for the pages_demo demonstrator — exercises the
generated ho_api/local_auth.py (DB password check), unlike blog_demo's
simplified yes-auth example.

  POST /auth/signup  {name, email, password}  → create user; first signup becomes admin
  POST /auth/login   {email, password}        → checks password via local_auth.authenticate()
  GET  /ho_users                              → list users with is_admin flag
"""
import os
import uuid
import bcrypt
import jwt
from litestar import get, post
from litestar.exceptions import HTTPException

from pages_demo import MODEL
from half_orm_gen.backend.ho_api.models import HoApiModels
from half_orm_gen.backend.ho_api.identity_models import HoIdentityModels
from ho_api.local_auth import authenticate


def _sign(user_id: str, roles: list[str], name: str | None = None, email: str | None = None) -> str:
    algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
    if algorithm == 'RS256':
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        key_file = os.path.join(cur_dir, os.pardir, os.environ['HO_JWT_PRIVATE_KEY_FILE'])
        with open(key_file) as f:
            key = f.read()
    else:
        key = os.environ['HO_JWT_SECRET']
    payload = {'sub': user_id, 'roles': roles}
    # name/email are only used by a peer we later delegate to (federation_callback
    # reads them to fill in a brand new "half_orm_meta.identity"."user" row it
    # creates for someone it's never seen before) — harmless extra claims here.
    if name:
        payload['name'] = name
    if email:
        payload['email'] = email
    return jwt.encode(payload, key, algorithm=algorithm)


@post('/auth/signup')
async def signup(data: dict) -> dict:
    """Create a new local user. Becomes admin if no admin exists yet."""
    email    = (data.get('email') or '').strip()
    name     = (data.get('name') or '').strip()
    password = data.get('password') or ''
    if not email or not name or not password:
        raise HTTPException(status_code=400, detail='name, email and password required')

    identity = HoIdentityModels(MODEL)
    existing = await identity.user()(email=email).ho_aselect('id')
    if existing:
        raise HTTPException(status_code=409, detail='Email already registered')

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user_id = str(uuid.uuid4())
    await identity.user()(
        id=user_id, name=name, email=email, password_hash=password_hash,
    ).ho_ainsert()

    api = HoApiModels(MODEL)
    admin_exists = await api.user_role()(role_name='admin').ho_aselect('user_id')
    role_name = 'admin' if not admin_exists else 'connected'
    await api.user_role()(user_id=user_id, role_name=role_name).ho_ainsert()

    return {'token': _sign(user_id, [role_name], name, email)}


@post('/auth/login')
async def login(data: dict) -> dict:
    """Real local login: checks the password against half_orm_meta.identity.user."""
    email    = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        raise HTTPException(status_code=400, detail='email and password required')
    user_id = await authenticate(MODEL, email, password)
    if not user_id:
        raise HTTPException(status_code=401, detail='Invalid email or password')
    identity = HoIdentityModels(MODEL)
    user_rows = await identity.user()(id=user_id).ho_aselect('name')
    name = user_rows[0]['name'] if user_rows else None
    api = HoApiModels(MODEL)
    role_rows = await api.user_role()(user_id=user_id).ho_aselect('role_name')
    roles = [r['role_name'] for r in role_rows] or ['connected']
    return {'token': _sign(user_id, roles, name, email)}


@get('/ho_users')
async def ho_users() -> list:
    """Return all known users (local + federated-in) with their admin flag."""
    identity = HoIdentityModels(MODEL)
    users = await identity.user()().ho_aselect('id', 'name')
    api = HoApiModels(MODEL)
    admin_rows = await api.user_role()(role_name='admin').ho_aselect('user_id')
    admin_ids = {str(r['user_id']) for r in admin_rows}
    return [
        {'id': str(u['id']), 'name': u['name'] or '(unnamed)', 'is_admin': str(u['id']) in admin_ids}
        for u in users
    ]


routes = [signup, login, ho_users]
PYEOF

echo -e "${GREEN}✓ Auth routes written${NC}"

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "To start the backend:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && litestar --app ho_api.app:application run --debug --port 8001"
echo ""
echo "  (ho_api/.env uses an RS256 keypair for federation — regenerated on every rebuild;"
echo "   run 'make demo-federate' after both blog_demo and pages_demo are (re)generated)"
