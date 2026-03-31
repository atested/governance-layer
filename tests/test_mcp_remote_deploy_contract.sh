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
GOVMCP_REMOTE_AUTH_TOKEN=token GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8018 GOVMCP_LOG_LEVEL=ERROR \
  "$PYTHON_BIN" "$ROOT/mcp/remote_deploy.py" --print-contract >"$TMPDIR_LOCAL/missing.out" 2>"$TMPDIR_LOCAL/missing.err"
RC_MISSING=$?

GOVMCP_REMOTE_AUTH_TOKEN=token GOVMCP_PUBLIC_BASE_URL=http://example.test GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8018 GOVMCP_LOG_LEVEL=ERROR \
  "$PYTHON_BIN" "$ROOT/mcp/remote_deploy.py" --print-contract >"$TMPDIR_LOCAL/http.out" 2>"$TMPDIR_LOCAL/http.err"
RC_HTTP=$?
set -e

[ "$RC_MISSING" -ne 0 ] || { echo "FAIL: missing public base url unexpectedly succeeded"; exit 1; }
[ "$RC_HTTP" -ne 0 ] || { echo "FAIL: non-https public base url unexpectedly succeeded"; exit 1; }

grep -q "GOVMCP_PUBLIC_BASE_URL_MISSING" "$TMPDIR_LOCAL/missing.err" || { echo "FAIL: missing base url marker absent"; cat "$TMPDIR_LOCAL/missing.err"; exit 1; }
grep -q "GOVMCP_PUBLIC_BASE_URL_MUST_BE_HTTPS" "$TMPDIR_LOCAL/http.err" || { echo "FAIL: https marker absent"; cat "$TMPDIR_LOCAL/http.err"; exit 1; }

JSON_OUT="$(GOVMCP_REMOTE_AUTH_TOKEN=token GOVMCP_PUBLIC_BASE_URL=https://govmcp.example.test GOVMCP_HOST=127.0.0.1 GOVMCP_PORT=8018 GOVMCP_STREAMABLE_HTTP_PATH=/mcp "$PYTHON_BIN" "$ROOT/mcp/remote_deploy.py" --print-contract)"
python3 - <<'PY' "$JSON_OUT"
import json, sys
obj = json.loads(sys.argv[1])
assert obj["public_mcp_url"] == "https://govmcp.example.test/mcp", obj
assert obj["local_bind_url"] == "http://127.0.0.1:8018/mcp", obj
assert obj["tls_termination"] == "external_required", obj
print("PASS: remote GovMCP deploy contract check")
PY
