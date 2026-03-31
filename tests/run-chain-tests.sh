#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPEND="$ROOT/scripts/append-record.sh"
VERIFY="$ROOT/scripts/verify-chain.py"
CHAIN="$ROOT/LOGS/decision-chain.jsonl"

mkdir -p "$ROOT/LOGS"

# Start fresh chain for test
rm -f "$CHAIN"

# Build 3-record chain using existing FS_WRITE intents (reuse)
"$APPEND" "$ROOT/LOGS/t-fs-001.json" >/dev/null
"$APPEND" "$ROOT/LOGS/t-fs-002.json" >/dev/null
"$APPEND" "$ROOT/LOGS/t-fs-003.json" >/dev/null

# Verify good chain
python3 "$VERIFY" "$CHAIN" >/dev/null

echo "PASS: verify-chain on clean chain"

# Tamper: flip one character in line 2 (safe minimal edit)
tmp="$CHAIN.tmp"
awk 'NR==2{sub(/RC-FS-HIDDEN-PATH/,"RC-FS-HIDDEN-PATHX")} {print}' "$CHAIN" > "$tmp"
mv "$tmp" "$CHAIN"

set +e
python3 "$VERIFY" "$CHAIN" >/dev/null
rc=$?
set -e

if [[ "$rc" -eq 0 ]]; then
  echo "FAIL: tampered chain unexpectedly verified"
  exit 1
else
  echo "PASS: tampered chain detected"
fi
