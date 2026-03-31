#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${BOOTSTRAP_VENV_DIR:-$ROOT/.venv}"
PYTHON_BIN="${BOOTSTRAP_PYTHON_BIN:-python3}"
DRY_RUN=0
SKIP_BASE="${BOOTSTRAP_RELEASE_GATE_SKIP_BASE:-1}"
SKIP_INSTALL="${BOOTSTRAP_SKIP_INSTALL:-0}"

usage() {
  cat <<'EOF'
Usage: system/scripts/bootstrap-run.sh [--dry-run] [--venv DIR] [--python PYTHON]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --venv) VENV_DIR="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

run_cmd() {
  echo "$ $*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[exit=0]"
    return 0
  fi
  set +e
  "$@"
  local rc=$?
  set -e
  echo "[exit=$rc]"
  return "$rc"
}

cd "$ROOT"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: required python not found: $PYTHON_BIN" >&2
  exit 2
fi

echo "BOOTSTRAP_ROOT=$ROOT"
echo "BOOTSTRAP_VENV_DIR=$VENV_DIR"
echo "BOOTSTRAP_PYTHON_BIN=$PYTHON_BIN"
echo "BOOTSTRAP_RELEASE_GATE_SKIP_BASE=$SKIP_BASE"
echo "BOOTSTRAP_SKIP_INSTALL=$SKIP_INSTALL"
echo "BOOTSTRAP_EXPECTED_OUTPUT_DIR=out/proof-bundles/<run-id>/"

run_cmd "$PYTHON_BIN" -m venv "$VENV_DIR"
if [[ "$SKIP_INSTALL" == "1" ]]; then
  echo "INFO: bootstrap pip install skipped via BOOTSTRAP_SKIP_INSTALL=1"
else
  run_cmd "$VENV_DIR/bin/python" -m pip install -r "$ROOT/mcp/requirements.txt"
fi
run_cmd env RELEASE_GATE_SKIP_BASE="$SKIP_BASE" bash "$ROOT/system/scripts/release-gate.sh"
