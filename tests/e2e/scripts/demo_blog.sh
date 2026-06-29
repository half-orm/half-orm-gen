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

cat > "Patches/1-blog-schema/01_blog.sql" << 'SQL'
CREATE SCHEMA blog;
create schema actor;

CREATE TABLE actor.user (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name  TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE blog.post (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    author_id UUID REFERENCES actor.user(id) on delete cascade
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id) on delete cascade,
    author_id    UUID REFERENCES actor.user(id) on delete cascade,
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
half_orm gen api --litestar
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
# 11. Yes-auth routes (user file, not generated)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== YES-AUTH ROUTES ===${NC}"

cat > ho_api/custom/routes.py << 'PYEOF'
"""
Yes-auth routes for the blog_demo demonstrator.

NOT FOR PRODUCTION — authentication always succeeds (no password check).

  POST /auth/signup  {name, email}  → create user; first signup becomes admin
  POST /auth/login   {email}        → yes-auth login; user must exist
  GET  /ho_users                    → list users with is_admin flag
"""
import os
import jwt
from litestar import get, post
from litestar.exceptions import HTTPException

from blog_demo.actor.user import User
from blog_demo import MODEL
from half_orm_gen.backend.ho_api.models import HoApiModels


def _sign(user_id: str, roles: list[str]) -> str:
    secret    = os.environ['HO_JWT_SECRET']
    algorithm = os.environ.get('HO_JWT_ALGORITHM', 'HS256')
    return jwt.encode({'sub': user_id, 'roles': roles}, secret, algorithm=algorithm)


@post('/auth/signup')
async def signup(data: dict) -> dict:
    """Create a new user. Becomes admin if no admin exists yet."""
    email = (data.get('email') or '').strip()
    name  = (data.get('name')  or '').strip()
    if not email or not name:
        raise HTTPException(status_code=400, detail='name and email required')

    api = HoApiModels(MODEL)

    rows = await User(email=email).ho_aselect('id')
    if not rows:
        await User(name=name, email=email).ho_ainsert()
        rows = await User(email=email).ho_aselect('id')
    user_id = str(rows[0]['id'])

    role_rows = await api.user_role()(user_id=user_id).ho_aselect('role_name')
    if not role_rows:
        admin_exists = await api.user_role()(role_name='admin').ho_aselect('user_id')
        role_name = 'admin' if not admin_exists else 'connected'
        await api.user_role()(user_id=user_id, role_name=role_name).ho_ainsert()
        role_rows = await api.user_role()(user_id=user_id).ho_aselect('role_name')

    return {'token': _sign(user_id, [r['role_name'] for r in role_rows])}


@post('/auth/login')
async def login(data: dict) -> dict:
    """Yes-auth login: any registered user can log in by email (no password)."""
    email = (data.get('email') or '').strip()
    if not email:
        raise HTTPException(status_code=400, detail='email required')
    rows = await User(email=email).ho_aselect('id')
    if not rows:
        raise HTTPException(status_code=404, detail='User not found')
    user_id = str(rows[0]['id'])
    api = HoApiModels(MODEL)
    role_rows = await api.user_role()(user_id=user_id).ho_aselect('role_name')
    roles = [r['role_name'] for r in role_rows] or ['connected']
    return {'token': _sign(user_id, roles)}


@get('/ho_users')
async def ho_users() -> list:
    """Return all registered users with their admin flag."""
    users = await User().ho_aselect('id', 'name')
    api = HoApiModels(MODEL)
    admin_rows = await api.user_role()(role_name='admin').ho_aselect('user_id')
    admin_ids = {str(r['user_id']) for r in admin_rows}
    return [
        {'id': str(u['id']), 'name': u['name'], 'is_admin': str(u['id']) in admin_ids}
        for u in users
    ]


routes = [signup, login, ho_users]
PYEOF

echo -e "${GREEN}✓ Yes-auth routes written${NC}"

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "To start the backend:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && litestar --app ho_api.app:application run --reload"
echo ""
echo "  (ho_api/.env was generated with a random HO_JWT_SECRET — loaded automatically)"
