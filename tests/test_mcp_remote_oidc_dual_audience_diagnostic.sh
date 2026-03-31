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
  echo "ERROR: missing interpreter for OIDC verifier test" >&2
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
CANONICAL_AUDIENCE="https://govmcp.local/api"
RESOURCE_AUDIENCE="https://mac-mini.tail341fb0.ts.net/mcp"
WRONG_AUDIENCE="https://example.invalid/not-allowed"
SCOPE="govmcp:invoke"

cat >"$TMP_DIR/mock_oidc_issuer.py" <<'PY'
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

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
    encoding=Encoding.PEM,
    format=PrivateFormat.PKCS8,
    encryption_algorithm=NoEncryption(),
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

env TMP_DIR="$TMP_DIR" ISSUER_URL="$ISSUER_URL" CANONICAL_AUDIENCE="$CANONICAL_AUDIENCE" RESOURCE_AUDIENCE="$RESOURCE_AUDIENCE" WRONG_AUDIENCE="$WRONG_AUDIENCE" SCOPE="$SCOPE" ROOT="$ROOT" "$VENV_PY" - <<'PY'
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import jwt

root = Path(os.environ["ROOT"])
sys.path.insert(0, str(root / "mcp"))
import remote_server

private_key = (Path(os.environ["TMP_DIR"]) / "issuer_private_key.pem").read_text(encoding="utf-8")
runtime_dir = Path(os.environ["TMP_DIR"]) / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOVMCP_OIDC_DIAGNOSTICS"] = "1"
os.environ["GOVMCP_REMOTE_AUTH_MODE"] = "oidc"
os.environ["GOVMCP_OIDC_ISSUER_URL"] = os.environ["ISSUER_URL"]
os.environ["GOVMCP_OIDC_AUDIENCE"] = os.environ["CANONICAL_AUDIENCE"]
os.environ["GOVMCP_OIDC_REQUIRED_SCOPES"] = os.environ["SCOPE"]

def make_token(audience: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": os.environ["ISSUER_URL"],
            "aud": audience,
            "sub": "connector-user",
            "azp": "claude-remote-client",
            "scope": os.environ["SCOPE"],
            "exp": now + 3600,
            "iat": now,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )

async def check():
    verifier = remote_server._OIDCTokenVerifier(os.environ["ISSUER_URL"], os.environ["CANONICAL_AUDIENCE"])
    canonical = await verifier.verify_token(make_token(os.environ["CANONICAL_AUDIENCE"]))
    assert canonical is not None, "canonical audience token should pass"
    assert canonical.resource == os.environ["CANONICAL_AUDIENCE"], canonical
    print("PASS: canonical audience accepted")

    resource = await verifier.verify_token(make_token(os.environ["RESOURCE_AUDIENCE"]))
    assert resource is not None, "resource audience token should pass"
    assert resource.resource == os.environ["RESOURCE_AUDIENCE"], resource
    print("PASS: inspector resource audience accepted")

    rejected = await verifier.verify_token(make_token(os.environ["WRONG_AUDIENCE"]))
    assert rejected is None, "non-allowlisted audience token should fail"
    print("PASS: non-allowlisted audience rejected")

    diag_path = runtime_dir / "LOGS" / "oidc_live_diagnostics.jsonl"
    assert diag_path.exists(), "expected diagnostics log"
    rows = [json.loads(line) for line in diag_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    passed = [row for row in rows if row.get("event") == "oidc_validation_passed"]
    failed = [row for row in rows if row.get("event") == "oidc_validation_failed"]
    assert any(row.get("audience_matched") == os.environ["CANONICAL_AUDIENCE"] for row in passed), rows
    assert any(row.get("audience_matched") == os.environ["RESOURCE_AUDIENCE"] for row in passed), rows
    assert any(row.get("failure_reason") == "audience" for row in failed), rows
    assert any(row.get("token_present") is True for row in passed + failed), rows
    print("PASS: diagnostic audience match evidence emitted")

asyncio.run(check())
PY
