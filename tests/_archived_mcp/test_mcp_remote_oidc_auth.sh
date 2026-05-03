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
SCOPE="govmcp:invoke"

cat >"$TMP_DIR/mock_oidc_issuer.py" <<'PY'
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives.asymmetric import rsa

issuer = os.environ["ISSUER_URL"]
port = int(os.environ["ISSUER_PORT"])
tmp_dir = os.environ["TMP_DIR"]

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
private_numbers = key.private_numbers()
public_numbers = private_numbers.public_numbers

def b64u(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

jwks = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-key-1",
            "use": "sig",
            "alg": "RS256",
            "n": b64u(public_numbers.n),
            "e": b64u(public_numbers.e),
        }
    ]
}

private_pem = key.private_bytes(
    encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
    format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
    encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
)

with open(os.path.join(tmp_dir, "issuer_private_key.pem"), "wb") as fh:
    fh.write(private_pem)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            payload = {
                "issuer": issuer,
                "jwks_uri": f"{issuer}/jwks",
            }
        elif self.path == "/jwks":
            payload = jwks
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

ISSUER_URL="$ISSUER_URL" ISSUER_PORT="$ISSUER_PORT" TMP_DIR="$TMP_DIR" "$VENV_PY" "$TMP_DIR/mock_oidc_issuer.py" &
ISSUER_PID=$!

for _ in $(seq 1 50); do
  if curl -sS "${ISSUER_URL}/.well-known/openid-configuration" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

VALID_TOKEN="$(env TMP_DIR="$TMP_DIR" ISSUER_URL="$ISSUER_URL" AUDIENCE="$AUDIENCE" SCOPE="$SCOPE" "$VENV_PY" - <<'PY'
import os, time
from pathlib import Path
import jwt

private_key = Path(os.environ["TMP_DIR"]) / "issuer_private_key.pem"
token = jwt.encode(
    {
        "iss": os.environ["ISSUER_URL"],
        "aud": os.environ["AUDIENCE"],
        "sub": "connector-user",
        "azp": "claude-remote-client",
        "scope": os.environ["SCOPE"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    },
    private_key.read_text(encoding="utf-8"),
    algorithm="RS256",
    headers={"kid": "test-key-1"},
)
print(token)
PY
)"

export GOV_RUNTIME_DIR="$ROOT/gov_runtime"
export GOVMCP_REMOTE_AUTH_MODE="oidc"
export GOVMCP_OIDC_ISSUER_URL="$ISSUER_URL"
export GOVMCP_OIDC_AUDIENCE="$AUDIENCE"
export GOVMCP_OIDC_REQUIRED_SCOPES="$SCOPE"
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
  if curl -sS -o /dev/null "http://127.0.0.1:$REMOTE_PORT/.well-known/oauth-protected-resource/mcp" 2>/dev/null; then
    break
  fi
  sleep 0.1
done

env ISSUER_URL="$ISSUER_URL" PUBLIC_BASE_URL="$PUBLIC_BASE_URL" GOVMCP_PORT="$REMOTE_PORT" "$VENV_PY" - <<'PY'
import json, os, urllib.request
url = f"http://127.0.0.1:{os.environ['GOVMCP_PORT']}/.well-known/oauth-protected-resource/mcp"
payload = json.load(urllib.request.urlopen(url))
assert payload["authorization_servers"] == [os.environ["ISSUER_URL"].rstrip("/") + "/"], payload
assert payload["resource"] == f"{os.environ['PUBLIC_BASE_URL']}/mcp", payload
print("RESOURCE_METADATA_OK")
PY

NOAUTH_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$REMOTE_PORT/mcp")"
[ "$NOAUTH_STATUS" = "401" ] || { echo "expected 401, got $NOAUTH_STATUS" >&2; exit 1; }

WRONG_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer wrong-token' "http://127.0.0.1:$REMOTE_PORT/mcp")"
[ "$WRONG_STATUS" = "401" ] || { echo "expected 401, got $WRONG_STATUS" >&2; exit 1; }

env VALID_TOKEN="$VALID_TOKEN" GOVMCP_PORT="$REMOTE_PORT" "$VENV_PY" - <<'PY'
import asyncio, json, os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    url = f"http://127.0.0.1:{os.environ['GOVMCP_PORT']}/mcp"
    token = os.environ["VALID_TOKEN"]
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            resp = await session.call_tool(
                "fs_write",
                {
                    "path": "/tmp/govmcp-oidc-smoke-deny.txt",
                    "content": "oidc-smoke",
                    "overwrite": False,
                    "request_executable": False,
                },
            )
            payload = json.loads(resp.content[0].text)
            assert payload["policy_decision"] == "DENY", payload
            codes = {row.get("code") for row in payload.get("policy_reasons", [])}
            assert "RC-FS-PATH-DISALLOWED" in codes, payload
            print("PASS: remote GovMCP OIDC auth smoke")

asyncio.run(main())
PY
