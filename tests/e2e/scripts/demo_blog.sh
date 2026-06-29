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
# 11. Fake authorization middleware (user file, not generated)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== FAKE AUTH MIDDLEWARE ===${NC}"
mkdir -p ho_api/custom/middlewares
touch ho_api/custom/__init__.py
touch ho_api/custom/middlewares/__init__.py

cat > ho_api/custom/middlewares/authorization.py << 'PYEOF'
"""
Fake authorization middleware for the blog_demo demonstrator.

NOT FOR PRODUCTION — replaces real JWT validation.

Bearer token semantics:
  <user-uuid>   → look up actor.user + half_orm_meta.api.user_role;
                  set request.state.user + authorized_roles (expanded hierarchy)
  <role-name>   → pass through (bearer-as-role fallback in _get_roles handles it)
  (no token)    → anonymous
"""
import uuid as _uuid

from litestar.types import ASGIApp, Receive, Scope, Send


def _parse_uuid(token: str) -> str | None:
    try:
        return str(_uuid.UUID(token))
    except ValueError:
        return None


class Authorization:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            from litestar.connection import Request
            request = Request(scope)
            token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
            user_uuid = _parse_uuid(token) if token else None
            if user_uuid is not None:
                await self._resolve_user(scope, user_uuid)
        await self.app(scope, receive, send)

    async def _resolve_user(self, scope: Scope, user_uuid: str) -> None:
        from blog_demo.actor.user import User
        from blog_demo import MODEL
        from half_orm_gen.backend.ho_api.models import HoApiModels
        from half_orm_gen.backend.ho_api.loader import load_role_parents
        from half_orm_gen.backend.crud_helpers import _expand_roles

        rows = await User(id=user_uuid).ho_aselect('id')
        state: dict = scope.setdefault('state', {})
        if not rows:
            state['authorized_roles'] = ['anonymous']
            return

        api = HoApiModels(MODEL)
        role_rows = await api.user_role()(user_id=user_uuid).ho_aselect('role_name')
        explicit_roles = [r['role_name'] for r in role_rows] or ['connected']

        parent_map = await load_role_parents(MODEL)
        all_roles = _expand_roles(explicit_roles, parent_map)

        state['user'] = user_uuid
        state['authorized_roles'] = all_roles
PYEOF

mkdir -p ho_api/custom
touch ho_api/custom/__init__.py

cat > ho_api/custom/routes.py << 'PYEOF'
"""Custom routes for the blog_demo demonstrator."""
from litestar import get
from blog_demo.actor.user import User
from blog_demo import MODEL
from half_orm_gen.backend.ho_api.models import HoApiModels


@get('/ho_users')
async def ho_users() -> list:
    """Return all registered users with their admin flag. Used by the frontend role selector."""
    users = await User().ho_aselect('id', 'name')
    api = HoApiModels(MODEL)
    admin_rows = await api.user_role()(role_name='admin').ho_aselect('user_id')
    admin_ids = {str(r['user_id']) for r in admin_rows}
    return [
        {'id': str(u['id']), 'name': u['name'], 'is_admin': str(u['id']) in admin_ids}
        for u in users
    ]


routes = [ho_users]
PYEOF

echo -e "${GREEN}✓ Fake auth middleware written${NC}"

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "To start the server:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && half_orm gen run --reload"
