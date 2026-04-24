#!/usr/bin/env bash
set -euo pipefail
# observe-hook.sh — PostToolUse hook for reporting ungoverned operations
# Receives JSON on stdin from Claude Code with tool_name, tool_input, etc.
# Reads the dashboard token from gov_runtime/dashboard_token

RUNTIME_DIR="${GOV_RUNTIME_DIR:-/Volumes/SSD/archive/gov/governance-layer/gov_runtime}"
TOKEN_FILE="$RUNTIME_DIR/dashboard_token"
DASHBOARD_PORT="${DASHBOARD_PORT:-9700}"

# Read token; exit silently if unavailable
[ -f "$TOKEN_FILE" ] || exit 0
TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null)" || exit 0
[ -n "$TOKEN" ] || exit 0

# Read stdin (JSON from Claude Code hook system)
INPUT="$(cat)"

# Extract tool name and determine operation type + target
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)"
TARGET=""

case "$TOOL_NAME" in
  Read|Write|Edit)
    OP_TYPE="$(echo "$TOOL_NAME" | tr '[:upper:]' '[:lower:]')"
    TARGET="$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
    ;;
  Bash)
    OP_TYPE="execute"
    TARGET="$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
    ;;
  Glob)
    OP_TYPE="glob"
    TARGET="$(echo "$INPUT" | jq -r '(.tool_input.path // ".") + "/" + (.tool_input.pattern // "")' 2>/dev/null)"
    ;;
  Grep)
    OP_TYPE="grep"
    TARGET="$(echo "$INPUT" | jq -r '(.tool_input.path // ".") + " pattern:" + (.tool_input.pattern // "")' 2>/dev/null)"
    ;;
  *)
    OP_TYPE="${TOOL_NAME:-other}"
    ;;
esac

# Build JSON payload with target if available
if [ -n "$TARGET" ]; then
  # Escape target for JSON (handle quotes and backslashes)
  ESCAPED_TARGET="$(echo "$TARGET" | jq -Rs '.' | sed 's/^"//;s/"$//')"
  PAYLOAD="{\"operation_type\": \"${OP_TYPE}\", \"target\": \"${ESCAPED_TARGET}\", \"source\": \"claude_code_hook\"}"
else
  PAYLOAD="{\"operation_type\": \"${OP_TYPE}\", \"source\": \"claude_code_hook\"}"
fi

# Fire-and-forget observation report
curl -s -X POST "http://127.0.0.1:${DASHBOARD_PORT}/api/observe" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "$PAYLOAD" \
  > /dev/null 2>&1 &
