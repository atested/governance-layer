#!/usr/bin/env bash
# Check local prerequisites for the Design UI MCP server.

set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in
        /*) ;;
        *) SOURCE="$DIR/$SOURCE" ;;
    esac
done

SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
REPO_ROOT="$(cd -P "$SCRIPT_DIR/.." && pwd)"
DESIGN_UI_DIR="$REPO_ROOT/design-ui"
API_URL="${DESIGN_UI_API_URL:-http://127.0.0.1:4174/api}"

STATUS=0
DEPS_PRESENT=0

pass() {
    printf 'PASS: %s\n' "$1"
}

warn() {
    printf 'WARN: %s\n' "$1"
}

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    STATUS=1
}

if [ -f "$DESIGN_UI_DIR/package.json" ]; then
    pass "found $DESIGN_UI_DIR/package.json"
else
    fail "missing $DESIGN_UI_DIR/package.json"
fi

if [ -f "$DESIGN_UI_DIR/mcp/server.ts" ]; then
    pass "found $DESIGN_UI_DIR/mcp/server.ts"
else
    fail "missing $DESIGN_UI_DIR/mcp/server.ts"
fi

if command -v node >/dev/null 2>&1; then
    pass "node available: $(node --version)"
else
    fail "node not found on PATH"
fi

if command -v npm >/dev/null 2>&1; then
    pass "npm available: $(npm --version)"
else
    fail "npm not found on PATH"
fi

if [ -d "$DESIGN_UI_DIR/node_modules" ]; then
    pass "design-ui dependencies present"
    DEPS_PRESENT=1
elif [ -f "$DESIGN_UI_DIR/package-lock.json" ]; then
    warn "design-ui dependencies not installed; run: npm --prefix \"$DESIGN_UI_DIR\" install"
else
    fail "design-ui dependencies missing and package-lock.json not found"
fi

if command -v node >/dev/null 2>&1 && [ -f "$DESIGN_UI_DIR/mcp/server.ts" ] && [ "$DEPS_PRESENT" -eq 1 ]; then
    if (cd "$DESIGN_UI_DIR" && node --no-warnings -e "import('./mcp/server.ts')" >/dev/null 2>&1); then
        pass "MCP server imports successfully"
    else
        fail "MCP server import failed; install dependencies with npm --prefix \"$DESIGN_UI_DIR\" install"
    fi
elif command -v node >/dev/null 2>&1 && [ -f "$DESIGN_UI_DIR/mcp/server.ts" ]; then
    warn "MCP server import skipped until dependencies are installed"
fi

if command -v node >/dev/null 2>&1; then
    if DESIGN_UI_API_URL="$API_URL" node --input-type=module <<'NODE' >/dev/null 2>&1
const apiUrl = process.env.DESIGN_UI_API_URL;
try {
  const response = await fetch(apiUrl.replace(/\/+$/, "") + "/health");
  process.exit(response.ok ? 0 : 1);
} catch {
  process.exit(1);
}
NODE
    then
        pass "Design UI API reachable at $API_URL"
    else
        warn "Design UI API not reachable at $API_URL; start Design UI before using MCP tools"
    fi
fi

exit "$STATUS"
