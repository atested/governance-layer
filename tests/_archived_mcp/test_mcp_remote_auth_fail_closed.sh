#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="python3"
if [ -x "$ROOT/mcp/.venv/bin/python3" ]; then
  PYTHON_BIN="$ROOT/mcp/.venv/bin/python3"
fi

TMPDIR_LOCAL="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

set +e
GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8017 GOVMCP_LOG_LEVEL=ERROR \
  "$PYTHON_BIN" "$ROOT/mcp/remote_server.py" --print-config >"$TMPDIR_LOCAL/stdout.txt" 2>"$TMPDIR_LOCAL/stderr.txt"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  echo "FAIL: remote_server.py --print-config unexpectedly succeeded without auth config"
  exit 1
fi

if ! grep -q "GOVMCP_REMOTE_AUTH_TOKEN_MISSING" "$TMPDIR_LOCAL/stderr.txt"; then
  echo "FAIL: missing expected fail-closed auth marker"
  cat "$TMPDIR_LOCAL/stderr.txt"
  exit 1
fi

echo "PASS: remote GovMCP auth fail-closed config check"
