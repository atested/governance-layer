#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${GOV_RUNTIME_DIR:-$ROOT/.gov_runtime}"
VENV="$ROOT/mcp/.venv"
VENV_PY="$VENV/bin/python3"
PYTHON_BIN="python3"

mkdir -p "$RUNTIME/LOGS" "$RUNTIME/tmp"

if [ -x "$VENV_PY" ]; then
  PYTHON_BIN="$VENV_PY"
fi

if ! "$PYTHON_BIN" -c "from mcp import ClientSession" >/dev/null 2>&1; then
  echo "ERROR: Missing Python dependency 'mcp' for interpreter: $PYTHON_BIN" >&2
  if [ "$PYTHON_BIN" = "$VENV_PY" ]; then
    echo "Install once with: $VENV_PY -m pip install -r $ROOT/mcp/requirements.txt" >&2
  else
    echo "Create and install with: python3 -m venv $VENV && $VENV_PY -m pip install -r $ROOT/mcp/requirements.txt" >&2
  fi
  exit 1
fi

export GOV_RUNTIME_DIR="$RUNTIME"

"$PYTHON_BIN" "$ROOT/tests/run-mcp-smoke.py"
