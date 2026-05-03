#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT/mcp/.venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: missing interpreter $VENV_PY" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  if [ -n "${REMOTE_PID:-}" ]; then
    kill "$REMOTE_PID" 2>/dev/null || true
    wait "$REMOTE_PID" 2>/dev/null || true
  fi
  if [ -n "${ISSUER_PID:-}" ]; then
    kill "$ISSUER_PID" 2>/dev/null || true
    wait "$ISSUER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

PORTS="$("$VENV_PY" - <<'PY'
import socket
vals = []
for _ in range(2):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        vals.append(str(sock.getsockname()[1]))
print(" ".join(vals))
PY
)"
ISSUER_PORT="${PORTS%% *}"
REMOTE_PORT="${PORTS##* }"
ISSUER_URL="http://127.0.0.1:${ISSUER_PORT}"
PUBLIC_BASE_URL="https://govmcp.example.tailnet.ts.net"
AUDIENCE="govmcp-test-audience"

cat >"$TMP_DIR/mock_oidc_issuer.py" <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

issuer = os.environ["ISSUER_URL"]
port = int(os.environ["ISSUER_PORT"])
tmp_dir = os.environ["TMP_DIR"]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            payload = {
                "issuer": issuer + "/",
                "jwks_uri": f"{issuer}/jwks",
                "authorization_endpoint": f"{issuer}/oidc/authorize",
                "token_endpoint": f"{issuer}/oidc/token",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "token_endpoint_auth_methods_supported": ["none"],
                "code_challenge_methods_supported": ["S256"],
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

    def do_POST(self):
        if self.path != "/oidc/token":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode()
        with open(os.path.join(tmp_dir, "token_request_body.txt"), "w", encoding="utf-8") as fh:
            fh.write(body)
        payload = {
            "access_token": "issuer-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return

HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY

ISSUER_URL="$ISSUER_URL" ISSUER_PORT="$ISSUER_PORT" TMP_DIR="$TMP_DIR" "$VENV_PY" "$TMP_DIR/mock_oidc_issuer.py" &
ISSUER_PID=$!

for _ in $(seq 1 50); do
  if curl -sS "${ISSUER_URL}/.well-known/openid-configuration" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

export GOV_RUNTIME_DIR="$ROOT/gov_runtime"
export GOVMCP_REMOTE_AUTH_MODE="oidc"
export GOVMCP_OIDC_ISSUER_URL="$ISSUER_URL"
export GOVMCP_OIDC_AUDIENCE="$AUDIENCE"
export GOVMCP_PUBLIC_BASE_URL="$PUBLIC_BASE_URL"
export GOVMCP_HOST="127.0.0.1"
export GOVMCP_PORT="$REMOTE_PORT"
export GOVMCP_STREAMABLE_HTTP_PATH="/mcp"
export GOVMCP_LOG_LEVEL="ERROR"

"$VENV_PY" "$ROOT/mcp/remote_server.py" >"$TMP_DIR/remote.stdout" 2>"$TMP_DIR/remote.stderr" &
REMOTE_PID=$!

for _ in $(seq 1 50); do
  if ! kill -0 "$REMOTE_PID" 2>/dev/null; then
    echo "ERROR: remote server exited early" >&2
    cat "$TMP_DIR/remote.stdout" >&2 || true
    cat "$TMP_DIR/remote.stderr" >&2 || true
    exit 1
  fi
  if curl -sS -o /dev/null "http://127.0.0.1:$REMOTE_PORT/.well-known/oauth-authorization-server" 2>/dev/null; then
    break
  fi
  sleep 0.1
done

env GOVMCP_PORT="$REMOTE_PORT" PUBLIC_BASE_URL="$PUBLIC_BASE_URL" ISSUER_URL="$ISSUER_URL" "$VENV_PY" - <<'PY'
import json, os, urllib.request

base = f"http://127.0.0.1:{os.environ['GOVMCP_PORT']}"
payload = json.load(urllib.request.urlopen(f"{base}/.well-known/oauth-authorization-server"))
assert payload["issuer"] == os.environ["ISSUER_URL"] + "/", payload
assert payload["authorization_endpoint"] == f"{os.environ['PUBLIC_BASE_URL']}/authorize", payload
assert payload["token_endpoint"] == f"{os.environ['PUBLIC_BASE_URL']}/token", payload
assert "none" in payload["token_endpoint_auth_methods_supported"], payload

openid = json.load(urllib.request.urlopen(f"{base}/.well-known/openid-configuration"))
assert openid["authorization_endpoint"] == payload["authorization_endpoint"], openid
assert openid["token_endpoint"] == payload["token_endpoint"], openid
assert "none" in openid["token_endpoint_auth_methods_supported"], openid
print("AUTH_SERVER_METADATA_OK")
PY

AUTHORIZE_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$REMOTE_PORT/authorize?client_id=test-client&state=test-state")"
[ "$AUTHORIZE_STATUS" = "307" ] || { echo "expected 307, got $AUTHORIZE_STATUS" >&2; exit 1; }
AUTHORIZE_REDIRECT="$(curl -sS -o /dev/null -w '%{redirect_url}' "http://127.0.0.1:$REMOTE_PORT/authorize?client_id=test-client&state=test-state")"
[ "$AUTHORIZE_REDIRECT" = "${ISSUER_URL}/oidc/authorize?client_id=test-client&state=test-state" ] || {
  echo "unexpected authorize redirect: $AUTHORIZE_REDIRECT" >&2
  exit 1
}

TOKEN_BODY="grant_type=authorization_code&code=abc123&code_verifier=verifier456"
TOKEN_RESPONSE="$(curl -sS -X POST -H 'Content-Type: application/x-www-form-urlencoded' --data "$TOKEN_BODY" "http://127.0.0.1:$REMOTE_PORT/token")"
printf '%s' "$TOKEN_RESPONSE" | grep -q '"access_token": "issuer-access-token"'

RECORDED_BODY="$(cat "$TMP_DIR/token_request_body.txt")"
[ "$RECORDED_BODY" = "$TOKEN_BODY" ] || { echo "unexpected proxied token body: $RECORDED_BODY" >&2; exit 1; }

echo "PASS: OIDC authorization-server compatibility shim"
