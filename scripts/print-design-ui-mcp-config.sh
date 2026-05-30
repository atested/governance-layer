#!/usr/bin/env bash
# Print a ready-to-paste Codex MCP config snippet for Design UI.

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

if [ ! -f "$DESIGN_UI_DIR/package.json" ]; then
    cat >&2 <<EOF
print-design-ui-mcp-config.sh: design-ui/package.json not found.

Expected:
  $DESIGN_UI_DIR/package.json

Run this script from the governance-layer repo's scripts/ directory, or
invoke it by absolute path from its checked-in location.
EOF
    exit 2
fi

if [ ! -f "$DESIGN_UI_DIR/mcp/server.ts" ]; then
    cat >&2 <<EOF
print-design-ui-mcp-config.sh: design-ui/mcp/server.ts not found.

Expected:
  $DESIGN_UI_DIR/mcp/server.ts

The Design UI MCP implementation must be present before configuring Codex.
EOF
    exit 2
fi

cat <<EOF
# Design UI MCP config for Codex
#
# 1. Start Design UI first:
#      $REPO_ROOT/scripts/run-design-ui.sh
#
# 2. Paste this snippet into:
#      ~/.codex/config.toml
#
# 3. Restart Codex so it reloads MCP servers.
#
# Design UI API URL:
#      $API_URL

[mcp_servers.design-ui]
command = "npm"
args = ["--prefix", "$DESIGN_UI_DIR", "run", "mcp"]
env = { DESIGN_UI_API_URL = "$API_URL" }

# Notes:
# - Design UI must be running before these MCP tools can read state.
# - MCP can create pending proposals only.
# - Operator approval in Design UI is still required for committed changes.
EOF
