#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_VENV_PY="$ROOT/mcp/.venv/bin/python3"
ARCHIVE_VENV_PY="/Volumes/SSD/archive/gov/governance-layer/mcp/.venv/bin/python3"

if [ -x "$DEFAULT_VENV_PY" ]; then
  VENV_PY="$DEFAULT_VENV_PY"
elif [ -x "$ARCHIVE_VENV_PY" ]; then
  VENV_PY="$ARCHIVE_VENV_PY"
else
  echo "ERROR: missing interpreter for Inspector CORS test" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  if [ -n "${ISSUER_PID:-}" ]; then
    kill "$ISSUER_PID" 2>/dev/null || true
    wait "$ISSUER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

PORT="$("$VENV_PY" - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"

ISSUER_PORT="$PORT"
ISSUER_URL="http://127.0.0.1:${ISSUER_PORT}"
ALLOWED_ORIGIN="http://localhost:6274"
BLOCKED_ORIGIN="http://localhost:9999"

cat >"$TMP_DIR/mock_oidc_issuer.py" <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

issuer = os.environ["ISSUER_URL"]
port = int(os.environ["ISSUER_PORT"])

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            payload = {
                "issuer": issuer,
                "jwks_uri": f"{issuer}/jwks",
                "authorization_endpoint": f"{issuer}/authorize",
                "token_endpoint": f"{issuer}/token",
            }
        elif self.path == "/jwks":
            payload = {"keys": []}
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY

ISSUER_URL="$ISSUER_URL" ISSUER_PORT="$ISSUER_PORT" "$VENV_PY" "$TMP_DIR/mock_oidc_issuer.py" &
ISSUER_PID=$!

for _ in $(seq 1 50); do
  if curl -sS "${ISSUER_URL}/.well-known/openid-configuration" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

env ROOT="$ROOT" ISSUER_URL="$ISSUER_URL" ALLOWED_ORIGIN="$ALLOWED_ORIGIN" BLOCKED_ORIGIN="$BLOCKED_ORIGIN" "$VENV_PY" - <<'PY'
import os
import sys
from pathlib import Path

from starlette.testclient import TestClient

root = Path(os.environ["ROOT"])
sys.path.insert(0, str(root / "mcp"))
import remote_server

os.environ["GOVMCP_REMOTE_AUTH_MODE"] = "oidc"
os.environ["GOVMCP_OIDC_ISSUER_URL"] = os.environ["ISSUER_URL"]
os.environ["GOVMCP_OIDC_AUDIENCE"] = "https://govmcp.local/api"
os.environ["GOVMCP_PUBLIC_BASE_URL"] = "https://mac-mini.tail341fb0.ts.net"
os.environ["GOVMCP_HOST"] = "127.0.0.1"
os.environ["GOVMCP_PORT"] = "6100"
os.environ["GOVMCP_STREAMABLE_HTTP_PATH"] = "/mcp"
os.environ["GOVMCP_LOG_LEVEL"] = "ERROR"

app = remote_server.build_remote_app()
client = TestClient(app)

allowed_origin = os.environ["ALLOWED_ORIGIN"]
blocked_origin = os.environ["BLOCKED_ORIGIN"]

allowed = client.get(
    "/.well-known/oauth-protected-resource/mcp",
    headers={"Origin": allowed_origin},
)
assert allowed.status_code == 200, allowed.text
assert allowed.headers.get("access-control-allow-origin") == allowed_origin, allowed.headers
print("PASS: allowlisted Inspector origin accepted")

blocked = client.get(
    "/.well-known/oauth-protected-resource/mcp",
    headers={"Origin": blocked_origin},
)
assert blocked.status_code == 200, blocked.text
assert blocked.headers.get("access-control-allow-origin") is None, blocked.headers
print("PASS: non-allowlisted origin rejected")

preflight = client.options(
    "/mcp",
    headers={
        "Origin": allowed_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    },
)
assert preflight.status_code == 200, preflight.text
assert preflight.headers.get("access-control-allow-origin") == allowed_origin, preflight.headers
print("PASS: allowlisted Inspector preflight accepted")
PY
