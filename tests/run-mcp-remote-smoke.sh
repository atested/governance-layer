#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/mcp/.venv"
VENV_PY="$VENV/bin/python3"
PYTHON_BIN="python3"

if [ -x "$VENV_PY" ]; then
  PYTHON_BIN="$VENV_PY"
fi

if ! "$PYTHON_BIN" -c "from mcp.client.streamable_http import streamablehttp_client" >/dev/null 2>&1; then
  echo "ERROR: Missing Python dependency 'mcp' for interpreter: $PYTHON_BIN" >&2
  if [ "$PYTHON_BIN" = "$VENV_PY" ]; then
    echo "Install once with: $VENV_PY -m pip install -r $ROOT/mcp/requirements.txt" >&2
  else
    echo "Create and install with: python3 -m venv $VENV && $VENV_PY -m pip install -r $ROOT/mcp/requirements.txt" >&2
  fi
  exit 1
fi

"$PYTHON_BIN" "$ROOT/tests/run-mcp-remote-smoke.py"
