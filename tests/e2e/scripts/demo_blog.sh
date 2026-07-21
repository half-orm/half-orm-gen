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
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
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
    --password "$TEST_DB_PASSWORD" \
    --with-meta=half_orm_meta.identity.user

cd "$PROJECT"

# ---------------------------------------------------------------------------
# 3. First release
# ---------------------------------------------------------------------------
git checkout ho-prod
half_orm dev release create minor   # ho-release/0.1.0

# ---------------------------------------------------------------------------
# 5. Release 0.1.1: two chained patches — half_orm_meta.api/.identity schema
#    first, then the author FK that references it. Both patches are applied
#    and merged onto the SAME release before promoting once at the end.
#
#    Patch 2 exists because `half_orm gen api` creates half_orm_meta.api/
#    .identity via raw DDL (a live side-effect, not tracked by any patch) —
#    without a patch capturing that same DDL, the NEXT `patch apply` would
#    restore the DB from model/schema.sql (the last *merged* patch's tracked
#    snapshot) and silently wipe both schemas, since neither is in it.
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE gen API ===${NC}"

half_orm dev patch create 1-gen-api-schema

python3 -c "
from half_orm_gen.backend.ho_api.ddl import HO_API_DDL, HO_IDENTITY_DDL
open('Patches/1-gen-api-schema/01_schema.sql', 'w').write(HO_API_DDL + '\n' + HO_IDENTITY_DDL)
"

half_orm dev patch apply
git add .
git commit -m "Add half_orm_meta.api/.identity schema"

half_orm dev patch merge

# ---------------------------------------------------------------------------
# 4. Patch 1: blog schema
# ---------------------------------------------------------------------------
half_orm dev patch create 2-blog-schema

# author_id has no FK yet — "half_orm_meta.identity"."user" (the shared
# identity table, planning/identite_federee.md) doesn't exist until patch 2
# below creates it. No local actor.user table: this project uses the
# federated identity table as its only user store, not a separate copy.
cat > "Patches/2-blog-schema/01_blog.sql" << 'SQL'
CREATE SCHEMA blog;

CREATE TABLE blog.post (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    author_id UUID references "half_orm_meta.identity"."user" on delete cascade
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id) on delete cascade,
    author_id    UUID references "half_orm_meta.identity"."user" on delete cascade,
    comment_type TEXT REFERENCES blog.comment_type(name)
);
SQL

echo -e "${GREEN}=== APPLY PATCH 1 ===${NC}"
half_orm dev patch apply

echo -e "${GREEN}✓ Model classes generated in ${PROJECT}/blog/${NC}"

git add .
git commit -m "Add blog schema"
half_orm dev patch merge

half_orm dev patch create 3-gen-api-and-frontend

# File scaffolding only, no DB change — the DDL above already created the
# schemas, so _ensure_ho_api_schema's own execute_query calls are a no-op
# (CREATE ... IF NOT EXISTS).
half_orm gen api --litestar --federation
half_orm gen frontend --angular
half_orm gen frontend --svelte

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

git add .
git commit -m "Generate ho_api + ho_frontend (federation)"

# ---------------------------------------------------------------------------
# 8a. Dynamic role: author on blog.post
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
# 8b. Custom filter: published_posts on blog.post
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

git add .
git commit -m "..."
half_orm dev patch merge
half_orm dev release promote prod

# ---------------------------------------------------------------------------
# 7. Load fixtures (access rules + demo data)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== LOAD FIXTURES ===${NC}"
psql "$PROJECT" \
    -f "$FIXTURES_DIR/blog_demo_data.sql"
echo -e "${GREEN}✓ Fixtures loaded${NC}"

echo -e "${GREEN}✓ Custom filter written${NC}"

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "To start the backend:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && litestar --app ho_api.app:application run --reload"
echo ""
echo "  (ho_api/.env uses an RS256 keypair for federation — regenerated on every rebuild;"
echo "   run 'make demo-federate' after both blog_demo and pages_demo are (re)generated)"
