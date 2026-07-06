#!/usr/bin/env bash
# Demo script: blog example end-to-end
#
# Creates a half-orm-dev project with the blog schema, adds CRUD_ACCESS to
# the generated modules, then runs half_orm gen generate.
#
# Usage: bash demo_blog.sh
#        bash demo_blog.sh --cleanup   (drop DB + remove project dir only)

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
FIXTURES_DIR="$SCRIPT_DIR/../../../fixtures"
source "$SCRIPT_DIR/common.sh"

PROJECT="blog_demo"
DEMOS_DIR="$SCRIPT_DIR/demos"
GIT_BARE="/tmp/${PROJECT}.git"
export HALFORM_CONF_DIR="$DEMOS_DIR/.config"

# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------
cleanup() {
    echo -e "${YELLOW}=== CLEANUP ===${NC}"
    cd "$SCRIPT_DIR"
    rm -rf "$DEMOS_DIR/$PROJECT" "$DEMOS_DIR/.config" "$GIT_BARE"
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
# 4. Patch: blog schema
# ---------------------------------------------------------------------------
half_orm dev patch create 1-blog-schema

# author_id has no FK yet — "half_orm_meta.identity"."user" (the shared
# identity table, planning/identite_federee.md) doesn't exist until
# `half_orm gen api --federation` runs, further down. It's added by a
# second patch below. No local actor.user table: this project uses the
# federated identity table as its only user store, not a separate copy.
cat > "Patches/1-blog-schema/01_blog.sql" << 'SQL'
CREATE SCHEMA blog;

CREATE TABLE blog.post (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    author_id UUID
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id) on delete cascade,
    author_id    UUID,
    comment_type TEXT REFERENCES blog.comment_type(name)
);
SQL

# ---------------------------------------------------------------------------
# 5. Apply patch (generates Python model classes)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== APPLY PATCH ===${NC}"
half_orm dev patch apply

echo -e "${GREEN}✓ Model classes generated in ${PROJECT}/blog/${NC}"

# ---------------------------------------------------------------------------
# 6. Commit patch
# ---------------------------------------------------------------------------
git add .
git commit -m "Add blog schema" --no-verify

# ---------------------------------------------------------------------------
# 8. Merge patch + promote
# ---------------------------------------------------------------------------
half_orm dev patch merge

half_orm dev release promote prod

# ---------------------------------------------------------------------------
# 9. Generate gen API
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE gen API ===${NC}"
half_orm gen api --litestar --federation

# --federation scaffolds an RS256 keypair instead of a symmetric secret (see
# planning/identite_federee.md) — needed so pages_demo (a separate demo peer,
# demo_pages.sh) can verify tokens blog_demo issues, and vice versa, without
# sharing a secret. HO_PEER_URL is this project's own public base URL, used
# as the redirect_uri target when ANOTHER peer delegates a login to it — it
# must include the API version prefix (/v0) since federation.py's routes
# are mounted under it just like every other route (`gen api` defaults to
# api_version 0, see cli_extension.py), otherwise the redirect 404s.
# scaffold_api_dir already writes an empty `HO_PEER_URL=` placeholder line —
# replace it (sed) rather than appending a second one: the .env loader in
# app.py uses os.environ.setdefault() per line, so the first (empty) HO_PEER_URL
# would otherwise silently win over a second, appended one.
sed -i 's|^HO_PEER_URL=$|HO_PEER_URL=http://localhost:8000/v0|' ho_api/.env
echo -e "${GREEN}✓ Set HO_PEER_URL for federation${NC}"

# HO_PEER_NAME is this project's own self-declared name, shown to other
# peers via its registration card — not chosen by whoever registers it
# (planning/identite_federee.md section 4bis).
sed -i 's|^HO_PEER_NAME=$|HO_PEER_NAME=blog_demo|' ho_api/.env
echo -e "${GREEN}✓ Set HO_PEER_NAME for federation${NC}"

# `gen api --federation` always mints a FRESH RSA keypair + HO_PEER_ID —
# fine normally (scaffolded once, `.env` never overwritten), but `cleanup()`
# above deletes the whole project dir, so a full `make demo-blog` rebuild
# would otherwise get a new keypair every time: every session token already
# in a browser tab fails signature verification against the new public key,
# forcing a re-login on every rebuild (same class of problem as the
# HO_JWT_SECRET instability fixed earlier for the non-federated case).
# Fix: pin a fixed, dev-only keypair + HO_PEER_ID across rebuilds — never
# do this for a real deployment, only for a demo that gets wiped and
# regenerated on every test iteration.
cp "$FIXTURES_DIR/blog_demo_private_key.pem" ho_api/private_key.pem
cp "$FIXTURES_DIR/blog_demo_public_key.pem" ho_api/public_key.pem
sed -i 's|^HO_PEER_ID=.*$|HO_PEER_ID=11111111-1111-1111-1111-111111111111|' ho_api/.env
echo -e "${GREEN}✓ Pinned dev keypair + HO_PEER_ID (stable across rebuilds)${NC}"

# HO_FRONTEND_URL is where /auth/login sends the browser when THIS peer is
# the identity source for someone else's delegated login (the frontend
# shows the ordinary login form, then forwards the resulting token). Both
# demo frontends run side by side here; Angular is the one with peer/admin
# management, so it's the one used as the federation entry point.
sed -i 's|^HO_FRONTEND_URL=$|HO_FRONTEND_URL=http://localhost:4200|' ho_api/.env
echo -e "${GREEN}✓ Set HO_FRONTEND_URL for federation${NC}"

# ---------------------------------------------------------------------------
# 9b. Patch: add the author FKs now that half_orm_meta.identity."user" exists
#     — real referential integrity, not just logically-linked UUIDs. Must
#     run BEFORE `half_orm gen frontend` below, which introspects real FK
#     constraints to detect author_id as a foreign key (combobox, link, etc.).
#     A new patch requires being on a ho-release/X.Y.Z branch, not ho-prod
#     (where `release promote prod` above left us) — create one first. It
#     also requires a clean working tree — commit the files `gen api`
#     wrote (app.py, federation.py, keys, .env) first; the original script
#     never needed to since it never created a second patch afterwards.
# ---------------------------------------------------------------------------
git checkout ho-prod
half_orm dev release create patch   # ho-release/0.1.1

git add .
git commit -m "Generate ho_api (federation)" --no-verify
git push origin ho-release/0.1.1

half_orm dev patch create 2-blog-author-fk

cat > "Patches/2-blog-author-fk/01_fk.sql" << 'SQL'
ALTER TABLE blog.post
    ADD CONSTRAINT fk_post_author
    FOREIGN KEY (author_id) REFERENCES "half_orm_meta.identity"."user"(id);

ALTER TABLE blog.comment
    ADD CONSTRAINT fk_comment_author
    FOREIGN KEY (author_id) REFERENCES "half_orm_meta.identity"."user"(id);
SQL

echo -e "${GREEN}=== APPLY PATCH 2 ===${NC}"
half_orm dev patch apply

git add .
git commit -m "Add FK: blog.post/comment.author_id -> half_orm_meta.identity.user" --no-verify
half_orm dev patch merge
half_orm dev release promote prod

half_orm gen frontend --angular
half_orm gen frontend --svelte

# ---------------------------------------------------------------------------
# 10. Load fixtures (access rules + demo data)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== LOAD FIXTURES ===${NC}"
psql "$PROJECT" \
    -f "$FIXTURES_DIR/blog_demo_data.sql"
echo -e "${GREEN}✓ Fixtures loaded${NC}"

# ---------------------------------------------------------------------------
# 11a. Dynamic role: author on blog.post
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== DYNAMIC ROLE: author ===${NC}"

python3 - << 'PYEOF'
import re, pathlib

path = pathlib.Path('blog_demo/blog/post.py')
src  = path.read_text()

imports = """\
from half_orm_gen.tools import ho_api_role
"""

method = """\

    @ho_api_role('post_author')
    def _is_author(self, request, rows: list) -> set:
        user = request.state.user
        return {row['id'] for row in rows if row['author_id'] == user}
"""

# Insert import after the first #>>> marker (top-level)
src = re.sub(
    r'(#>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + imports + '\n',
    src, count=1
)
# Insert method after the inner #>>> marker (inside class __init__)
src = re.sub(
    r'(        #>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + method,
    src, count=1
)
path.write_text(src)
print('  patched blog_demo/blog/post.py')
PYEOF

echo -e "${GREEN}✓ Dynamic role written${NC}"

# ---------------------------------------------------------------------------
# 11b. Custom filter: published_posts on blog.post
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== CUSTOM FILTER: published_posts ===${NC}"

python3 - << 'PYEOF'
import re, pathlib

path = pathlib.Path('blog_demo/blog/post.py')
src  = path.read_text()

imports = """\
from half_orm_gen.tools import ho_api_filter
"""

method = """\

    @ho_api_filter('published_posts')
    def _is_published(self, request):
        user = getattr(request.state, 'user', None)
        visible = self.__class__(published=True)
        if user:
            visible |= self.__class__(author_id=user)
        return self & visible
"""

# Insert import after the first #>>> marker (top-level)
src = re.sub(
    r'(#>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + imports + '\n',
    src, count=1
)
# Insert method after the inner #>>> marker (inside class __init__)
src = re.sub(
    r'(        #>>> PLACE YOUR CODE BELOW THIS LINE\. DO NOT REMOVE THIS LINE!\n)',
    r'\1' + method,
    src, count=1
)
path.write_text(src)
print('  patched blog_demo/blog/post.py')
PYEOF

echo -e "${GREEN}✓ Custom filter written${NC}"

# ---------------------------------------------------------------------------
# 11. Real local-auth routes (user file, not generated) — backed by
#     half_orm_meta.identity."user" (bcrypt password check via the generated
#     ho_api/local_auth.py), shared with pages_demo through federation.
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== AUTH ROUTES (real local auth) ===${NC}"

cat > ho_api/custom/routes.py << 'PYEOF'
"""
Real local-auth routes for the blog_demo demonstrator — signup/login backed
by half_orm_meta.identity."user" (bcrypt password check via the generated
ho_api/local_auth.py), shared with pages_demo through identity federation.

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

from blog_demo import MODEL
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
echo "  cd ${DEMOS_DIR}/${PROJECT} && litestar --app ho_api.app:application run --reload"
echo ""
echo "  (ho_api/.env uses an RS256 keypair for federation — regenerated on every rebuild;"
echo "   run 'make demo-federate' after both blog_demo and pages_demo are (re)generated)"
