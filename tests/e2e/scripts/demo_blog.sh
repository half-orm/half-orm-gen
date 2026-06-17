#!/usr/bin/env bash
# Demo script: blog example end-to-end
#
# Creates a half-orm-dev project with the blog schema, adds CRUD_ACCESS to
# the generated modules, then runs half_orm litestar generate.
#
# Usage: bash demo_blog.sh
#        bash demo_blog.sh --cleanup   (drop DB + remove project dir only)

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
source "$SCRIPT_DIR/common.sh"

PROJECT="blog_demo"
GIT_BARE="/tmp/${PROJECT}.git"
export HALFORM_CONF_DIR="$SCRIPT_DIR/.config"

# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------
cleanup() {
    echo -e "${YELLOW}=== CLEANUP ===${NC}"
    cd "$SCRIPT_DIR"
    rm -rf "$PROJECT" .config "$GIT_BARE"
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
    author_id UUID REFERENCES blog.author(id)
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id),
    author_id    UUID REFERENCES blog.author(id),
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
# 6. Add CRUD_ACCESS to developer spaces in each module
#    The developer space is between the first # >>> and # <<< markers.
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== ADD CRUD_ACCESS TO MODULES ===${NC}"

# Helper: insert Python code after the first "# >>>" line in a file
insert_crud_access() {
    local file="$1"
    local code="$2"
    python3 - "$file" "$code" << 'PYEOF'
import sys

filepath = sys.argv[1]
code = sys.argv[2]

with open(filepath) as f:
    lines = f.readlines()

occurrences = [i for i, line in enumerate(lines) if line.startswith('#>>>')]
# The first occurrence is in the docstring (example); the second is the real marker.
if len(occurrences) < 2:
    print(f"WARNING: less than 2 '#>>>' markers found in {filepath}", file=sys.stderr)
    sys.exit(0)
insert_after = occurrences[1]

if insert_after is None:
    print(f"WARNING: no '# >>>' marker found in {filepath}", file=sys.stderr)
    sys.exit(0)

new_lines = lines[:insert_after + 1] + ['\n', code, '\n'] + lines[insert_after + 1:]
with open(filepath, 'w') as f:
    f.writelines(new_lines)

print(f"  patched  {filepath}")
PYEOF
}

insert_crud_access "${PROJECT}/blog/author.py" \
'CRUD_ACCESS = {
    "GET":    {"public": ["id", "name"], "connected": ["id", "name", "email"]},
    "POST":   {"connected": {"in": ["name", "email"]}},
    "PUT":    {"connected": {"in": ["name", "email"]}},
    "DELETE": {"admin": None},
}'

insert_crud_access "${PROJECT}/blog/post.py" \
'CRUD_ACCESS = {
    "GET":    {"public": ["id", "title", "published", "author_id"], "connected": None},
    "POST":   {"connected": {"in": ["title", "content", "author_id"]}},
    "PUT":    {"connected": {"in": ["title", "content", "published"]}},
    "DELETE": {"admin": None},
}'

insert_crud_access "${PROJECT}/blog/comment.py" \
'CRUD_ACCESS = {
    "GET":    {"public": ["id", "content", "post_id", "author_id", "comment_type"]},
    "POST":   {"connected": {"in": ["content", "post_id", "author_id", "comment_type"]}},
    "DELETE": {"admin": None},
}'

insert_crud_access "${PROJECT}/blog/comment_type.py" \
'CRUD_ACCESS = {
    "GET": {"public": None},
}'

echo -e "${GREEN}✓ CRUD_ACCESS added${NC}"

# ---------------------------------------------------------------------------
# 7. Commit patch
# ---------------------------------------------------------------------------
git add .
git commit -m "Add blog schema and CRUD_ACCESS" --no-verify

# ---------------------------------------------------------------------------
# 8. Merge patch + promote
# ---------------------------------------------------------------------------
half_orm dev patch merge

half_orm dev release promote prod

# ---------------------------------------------------------------------------
# 9. Generate Litestar API
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE LITESTAR API ===${NC}"
half_orm litestar generate

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
echo "  cd ${PROJECT}"
echo "  half_orm litestar run --reload"
