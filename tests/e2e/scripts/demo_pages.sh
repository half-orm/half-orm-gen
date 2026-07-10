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
    --password "$TEST_DB_PASSWORD" \
    --with-meta=half_orm_meta.identity.user

cd "$PROJECT"

# ---------------------------------------------------------------------------
# 3. First release
# ---------------------------------------------------------------------------
git checkout ho-prod
half_orm dev release create minor   # ho-release/0.1.0

# ---------------------------------------------------------------------------
# 4. Patch 1: half_orm_meta.api/.identity schema — must exist before the wiki
#    schema below, since wiki.page.author_id references
#    "half_orm_meta.identity"."user" directly in its CREATE TABLE (inline FK,
#    not a separate ALTER TABLE patch afterward).
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE gen API SCHEMA ===${NC}"

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
# 5. Patch 2: wiki schema — author_id references half_orm_meta.identity."user"
#    directly, real referential integrity from the start.
# ---------------------------------------------------------------------------
half_orm dev patch create 2-wiki-schema

cat > "Patches/2-wiki-schema/01_wiki.sql" << 'SQL'
CREATE SCHEMA wiki;

CREATE TABLE wiki.page (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT NOT NULL,
    author_id UUID references "half_orm_meta.identity"."user" on delete cascade
);
SQL

echo -e "${GREEN}=== APPLY PATCH 2 ===${NC}"
half_orm dev patch apply

git add .
git commit -m "Add wiki schema"
half_orm dev patch merge

# ---------------------------------------------------------------------------
# 6. Patch 3: generate ho_api + ho_frontend (federation), load fixtures,
#    write the dynamic role — all inside one patch's create/.../merge cycle
#    rather than as loose commits directly on the release branch (which
#    breaks the next patch's ability to be created/replayed).
# ---------------------------------------------------------------------------
half_orm dev patch create 3-gen-api-and-frontend

# File scaffolding only, no DB change — the DDL from patch 1 already created
# the schemas, so _ensure_ho_api_schema's own execute_query calls are a no-op
# (CREATE ... IF NOT EXISTS).
half_orm gen api --litestar --federation
half_orm gen frontend --angular
half_orm gen frontend --svelte

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

git add .
git commit -m "Generate ho_api + ho_frontend (federation)"

# ---------------------------------------------------------------------------
# 7. Load fixtures (access rules + demo data)
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== LOAD FIXTURES ===${NC}"
psql "$PROJECT" \
    -f "$FIXTURES_DIR/pages_demo_data.sql"
echo -e "${GREEN}✓ Fixtures loaded${NC}"

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

git add .
git commit -m "Add page_author dynamic role"
half_orm dev patch merge
half_orm dev release promote prod

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "To start the backend:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && litestar --app ho_api.app:application run --debug --port 8001"
echo ""
echo "  (ho_api/.env uses an RS256 keypair for federation — regenerated on every rebuild;"
echo "   run 'make demo-federate' after both blog_demo and pages_demo are (re)generated)"
