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

CREATE TABLE blog.author (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name  TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE blog.post (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    author_id UUID REFERENCES blog.author(id) on delete cascade
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id) on delete cascade,
    author_id    UUID REFERENCES blog.author(id) on delete cascade,
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
    -f "$FIXTURES_DIR/blog_demo_access.sql" \
    -f "$FIXTURES_DIR/blog_demo_data.sql"
echo -e "${GREEN}✓ Fixtures loaded${NC}"

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo ""
echo "Generated files:"
echo "  ${PROJECT}/api/app.py"
echo "  ${PROJECT}/api/roles/core.py"
echo "  ${PROJECT}/api/guards.py"
echo "  ${PROJECT}/api/custom/routes.py"
echo ""
echo "To start the server:"
echo "  cd ${DEMOS_DIR}/${PROJECT} && half_orm gen run --reload"
