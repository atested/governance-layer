#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT/mcp/.venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: missing interpreter $VENV_PY" >&2
  exit 1
fi

TOKEN="govmcp-public-host-test-token"
PORT="$("$VENV_PY" - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"

TMP_DIR="$(mktemp -d)"
trap 'if [ -n "${SERVER_PID:-}" ]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi; rm -rf "$TMP_DIR"' EXIT

export GOV_RUNTIME_DIR="$ROOT/gov_runtime"
export GOVMCP_HOST="127.0.0.1"
export GOVMCP_PORT="$PORT"
export GOVMCP_STREAMABLE_HTTP_PATH="/mcp"
export GOVMCP_LOG_LEVEL="ERROR"
export GOVMCP_REMOTE_AUTH_TOKEN="$TOKEN"
export GOVMCP_PUBLIC_BASE_URL="https://example-public.tailnet.ts.net"

"$VENV_PY" "$ROOT/mcp/remote_server.py" >"$TMP_DIR/stdout.log" 2>"$TMP_DIR/stderr.log" &
SERVER_PID=$!

for _ in $(seq 1 50); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: remote server exited early" >&2
    cat "$TMP_DIR/stdout.log" >&2 || true
    cat "$TMP_DIR/stderr.log" >&2 || true
    exit 1
  fi
  if curl -sS -o /dev/null "http://127.0.0.1:$PORT/mcp" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

NOAUTH_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Host: example-public.tailnet.ts.net' "http://127.0.0.1:$PORT/mcp")"
[ "$NOAUTH_STATUS" = "401" ] || { echo "expected 401, got $NOAUTH_STATUS" >&2; exit 1; }

WRONG_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Host: example-public.tailnet.ts.net' -H 'Authorization: Bearer wrong-token' "http://127.0.0.1:$PORT/mcp")"
[ "$WRONG_STATUS" = "401" ] || { echo "expected 401, got $WRONG_STATUS" >&2; exit 1; }

AUTH_STATUS="$(curl -sS -o "$TMP_DIR/auth.body" -w '%{http_code}' -H 'Host: example-public.tailnet.ts.net' -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/mcp")"
[ "$AUTH_STATUS" = "406" ] || { echo "expected 406, got $AUTH_STATUS" >&2; cat "$TMP_DIR/auth.body" >&2 || true; exit 1; }

echo "PASS: public host header accepted by remote streamable-http surface"
