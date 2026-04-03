#!/bin/bash
# observe-hook.sh — PostToolUse hook for reporting ungoverned operations
# Usage: observe-hook.sh <operation_type>
# Reads the dashboard token from gov_runtime/dashboard_token

OP_TYPE="${1:-other}"
RUNTIME_DIR="${GOV_RUNTIME_DIR:-/Volumes/SSD/archive/gov/governance-layer/gov_runtime}"
TOKEN_FILE="$RUNTIME_DIR/dashboard_token"
DASHBOARD_PORT="${DASHBOARD_PORT:-9700}"

# Read token; exit silently if unavailable
[ -f "$TOKEN_FILE" ] || exit 0
TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null)" || exit 0
[ -n "$TOKEN" ] || exit 0

# Fire-and-forget observation report
curl -s -X POST "http://127.0.0.1:${DASHBOARD_PORT}/api/observe" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"operation_type\": \"${OP_TYPE}\", \"source\": \"claude_code_hook\"}" \
  > /dev/null 2>&1 &
