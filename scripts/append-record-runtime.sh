#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"

RUNTIME="${GOV_RUNTIME_DIR:-/Volumes/SSD/archive/gov/runtime}"
CHAIN="$RUNTIME/LOGS/decision-chain.jsonl"

# Resolve placeholder tokens for policy-eval allow_base_dirs
export GOV_CANONICAL_REPO_PATH="${GOV_CANONICAL_REPO_PATH:-$ROOT}"
export GOV_RUNTIME_PATH="${GOV_RUNTIME_PATH:-$RUNTIME}"

if [[ $# -ne 1 ]]; then
  echo "Usage: append-record-runtime.sh <intent.json>" >&2
  exit 2
fi

INTENT="$1"
mkdir -p "$RUNTIME/LOGS"

# Portable exclusive lock using mkdir (atomic on all POSIX systems).
# Prevents chain corruption when multiple processes append concurrently.
LOCKDIR="$CHAIN.lock.d"
_max_wait=50
_waited=0
while ! mkdir "$LOCKDIR" 2>/dev/null; do
  _waited=$((_waited + 1))
  if [[ $_waited -ge $_max_wait ]]; then
    echo "ERROR: timed out waiting for chain lock ($LOCKDIR)" >&2
    exit 1
  fi
  sleep 0.1
done
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

prev=""
if [[ -f "$CHAIN" ]] && [[ -s "$CHAIN" ]]; then
  # File exists and is not empty
  prev="$(tail -n 1 "$CHAIN" | python3 -c 'import json,sys; line=sys.stdin.read().strip(); print(json.loads(line)["record_hash"] if line else "")' || true)"
fi

if [[ -n "$prev" ]]; then
  export GOV_PREV_RECORD_HASH="$prev"
fi

rec="$("$EVAL" "$REG" "$INTENT")"

# Single-line canonical JSON for stable chain
one_line="$(echo "$rec" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False))')"

echo "$one_line" >> "$CHAIN"
echo "$one_line"
