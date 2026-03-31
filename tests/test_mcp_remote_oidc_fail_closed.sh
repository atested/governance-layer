#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT/mcp/.venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: missing interpreter $VENV_PY" >&2
  exit 1
fi

export GOVMCP_REMOTE_AUTH_MODE="oidc"
export GOVMCP_HOST="127.0.0.1"
export GOVMCP_PORT="8000"
export GOVMCP_STREAMABLE_HTTP_PATH="/mcp"
export GOVMCP_LOG_LEVEL="ERROR"

set +e
OUT="$("$VENV_PY" "$ROOT/mcp/remote_server.py" --print-config 2>&1)"
RC=$?
set -e

[ "$RC" -ne 0 ] || { echo "expected failure when OIDC config is missing" >&2; exit 1; }
printf '%s\n' "$OUT" | grep -q 'GOVMCP_OIDC_ISSUER_URL_MISSING'
echo "PASS: OIDC mode fails closed when issuer config is missing"
