#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/capabilities/capability-registry.json"
EVAL="$ROOT/scripts/policy-eval.py"
CHAIN="$ROOT/LOGS/decision-chain.jsonl"

if [[ $# -ne 1 ]]; then
  echo "Usage: append-record.sh <intent.json>" >&2
  exit 2
fi

INTENT="$1"
mkdir -p "$ROOT/LOGS"

prev=""
if [[ -f "$CHAIN" ]]; then
  # get last record_hash from last non-empty line
  prev="$(tail -n 1 "$CHAIN" | python3 -c 'import json,sys; line=sys.stdin.read().strip(); print(json.loads(line).get("record_hash","") if line else "")')"
fi

if [[ -n "$prev" ]]; then
  export GOV_PREV_RECORD_HASH="$prev"
fi

# Emit record and append as single-line canonical JSON for stable chaining
rec="$("$EVAL" "$REG" "$INTENT")"
one_line="$(echo "$rec" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False))')"
echo "$one_line" >> "$CHAIN"
echo "$one_line"
