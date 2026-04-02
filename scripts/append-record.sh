#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"
CHAIN="$ROOT/LOGS/decision-chain.jsonl"

# Resolve placeholder tokens for policy-eval allow_base_dirs
export GOV_CANONICAL_REPO_PATH="${GOV_CANONICAL_REPO_PATH:-$ROOT}"
export GOV_RUNTIME_PATH="${GOV_RUNTIME_PATH:-$ROOT}"

if [[ $# -ne 1 ]]; then
  echo "Usage: append-record.sh <intent.json>" >&2
  exit 2
fi

INTENT="$1"
# Restrict file creation permissions — chain, sidecars, logs
# should be owner-only (0600 files, 0700 dirs).
umask 0077
mkdir -p "$ROOT/LOGS"

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
  prev="$(tail -n 1 "$CHAIN" | python3 -c 'import json,sys; line=sys.stdin.read().strip(); print(json.loads(line)["record_hash"] if line else "")' || true)"
fi

if [[ -n "$prev" ]]; then
  export GOV_PREV_RECORD_HASH="$prev"
fi

# Emit record and append as single-line canonical JSON for stable chaining
rec="$("$EVAL" "$REG" "$INTENT")"
one_line="$(echo "$rec" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False))')"
echo "$one_line" >> "$CHAIN"

# Update chain_meta.json with current chain length for truncation detection.
CHAIN_META="$ROOT/LOGS/chain_meta.json"
CHAIN_LEN="$(grep -c '.' "$CHAIN" 2>/dev/null || echo 0)"
printf '{\n  "chain_length": %d\n}\n' "$CHAIN_LEN" > "$CHAIN_META.tmp"
chmod 600 "$CHAIN_META.tmp"
mv "$CHAIN_META.tmp" "$CHAIN_META"

echo "$one_line"
