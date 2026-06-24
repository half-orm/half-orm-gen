#!/usr/bin/env bash
# Generic demo script: creates a half-orm-dev project from a project name and SQL file.
#
# Usage:
#   bash demo_custom.sh <project_name> <sql_file>
#   bash demo_custom.sh <project_name> <sql_file> --cleanup

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <project_name> <sql_file> [--cleanup]" >&2
    exit 1
fi

PROJECT="$1"
SQL_FILE="$2"

if [[ "${3:-}" != "--cleanup" && ! -f "$SQL_FILE" ]]; then
    echo "Error: SQL file not found: $SQL_FILE" >&2
    exit 1
fi

DEMOS_DIR="$SCRIPT_DIR/demos"
GIT_BARE="/tmp/${PROJECT}.git"
export HALFORM_CONF_DIR="$DEMOS_DIR/.config"

# ---------------------------------------------------------------------------
# Cleanup
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

if [[ "${3:-}" == "--cleanup" ]]; then
    cleanup
    exit 0
fi

cleanup

# ---------------------------------------------------------------------------
# 1. DB user + DB + git bare repo
# ---------------------------------------------------------------------------
setup_test_db_user
createdb $PROJECT
psql $PROJECT -h localhost -U "$TEST_DB_USER" -f $SQL_FILE
git init --bare "$GIT_BARE"

# ---------------------------------------------------------------------------
# 2. Project init
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
# 7. Generate
# ---------------------------------------------------------------------------
echo -e "${GREEN}=== GENERATE ===${NC}"
half_orm gen api --litestar
half_orm gen frontend --angular
half_orm gen frontend --svelte

echo ""
echo -e "${GREEN}=== DONE ===${NC}"
echo "  cd ${DEMOS_DIR}/${PROJECT} && half_orm gen run --reload"
