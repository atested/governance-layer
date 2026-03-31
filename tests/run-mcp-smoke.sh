#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${GOV_RUNTIME_DIR:-/Volumes/SSD/archive/gov/runtime}"
VENV="$ROOT/mcp/.venv"

mkdir -p "$RUNTIME/LOGS" "$RUNTIME/tmp"

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python3 -m pip install -U pip >/dev/null
python3 -m pip install -r "$ROOT/mcp/requirements.txt" >/dev/null

export GOV_RUNTIME_DIR="$RUNTIME"

python3 "$ROOT/tests/run-mcp-smoke.py"
