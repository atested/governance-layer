#!/usr/bin/env bash
# test_replay.sh — Replay verifier tests for governance decision records.
#
# T-REPLAY-001: Replay a known DENY record (FS_WRITE overwrite-mismatch).
#   Expect: replay-record.py exit 0 and PASS output.
#
# T-REPLAY-002: Replay a known ALLOW record (FS_READ within caps).
#   Expect: exit 0 and PASS output.
#
# T-REPLAY-003 (tamper): Flip one char in request_bytes_b64 of a record.
#   Expect: exit 2 with "request_hash mismatch" message (fail-closed).
#
# T-REPLAY-004 (registry drift): Documented as future work.
#   Requires either a GOV_CAP_REGISTRY_PATH env override in policy-eval or
#   a controlled filesystem overlay to swap the on-disk registry without
#   touching the real file. Skipped here to avoid mutating working tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"

pass=0
fail=0

check_exit () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_contains () {
  local name="$1" text="$2" expect="$3"
  if echo "$text" | grep -q "$expect"; then
    echo "PASS: $name (contains '$expect')"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing '$expect')"
    echo "$text"
    fail=$((fail+1))
  fi
}

verify_hash () {
  local name="$1" json_file="$2"
  if "$VERIFY" "$json_file" >/dev/null 2>&1; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    "$VERIFY" "$json_file" || true
    fail=$((fail+1))
  fi
}

mkdir -p "$ROOT/LOGS"

# ---------------------------------------------------------------------------
# T-REPLAY-001: Replay a DENY record
# Source: canon_001a.json (FS_WRITE overwrite mismatch → DENY RC-FS-OVERWRITE-DISALLOWED)
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-001: replay DENY record ---"

python3 "$EVAL" "$FIXTURES/canon_001a.json" > "$ROOT/LOGS/t-replay-001.record.json"
verify_hash "T-REPLAY-001 baseline verify-record" "$ROOT/LOGS/t-replay-001.record.json"

out_001="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-001.record.json" 2>&1)"
rc_001=$?
check_exit  "T-REPLAY-001 exit 0"     "$rc_001"  "0"
assert_contains "T-REPLAY-001 PASS output" "$out_001" "PASS: replay matches original"
assert_contains "T-REPLAY-001 shows DENY"  "$out_001" "decision=DENY"
assert_contains "T-REPLAY-001 shows RC"    "$out_001" "RC-FS-OVERWRITE-DISALLOWED"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-002: Replay an ALLOW record
# Source: canon_002a.json (FS_READ max_bytes=4096, valid path → ALLOW)
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-002: replay ALLOW record ---"

python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$ROOT/LOGS/t-replay-002.record.json"
verify_hash "T-REPLAY-002 baseline verify-record" "$ROOT/LOGS/t-replay-002.record.json"

out_002="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-002.record.json" 2>&1)"
rc_002=$?
check_exit  "T-REPLAY-002 exit 0"      "$rc_002"  "0"
assert_contains "T-REPLAY-002 PASS output" "$out_002" "PASS: replay matches original"
assert_contains "T-REPLAY-002 shows ALLOW" "$out_002" "decision=ALLOW"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-003: Tamper test — flip one char in request_bytes_b64
# Expected: exit 2 with "request_hash mismatch" (fail-closed before evaluation).
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-003: tamper request_bytes_b64 → fail-closed ---"

# Produce a fresh DENY record to tamper with.
python3 "$EVAL" "$FIXTURES/canon_001a.json" > "$ROOT/LOGS/t-replay-003-original.record.json"

# Flip the last character of request_bytes_b64 (stay in valid base64 charset).
python3 - <<'PY' "$ROOT/LOGS/t-replay-003-original.record.json" "$ROOT/LOGS/t-replay-003-tampered.record.json"
import base64, json, sys

src, dst = sys.argv[1], sys.argv[2]
with open(src) as f:
    rec = json.load(f)

# Decode bytes, flip one byte in the middle, re-encode → valid base64, wrong hash.
raw = bytearray(base64.b64decode(rec["request_bytes_b64"]))
mid = len(raw) // 2
raw[mid] = (raw[mid] ^ 0xFF) & 0xFF
rec["request_bytes_b64"] = base64.b64encode(bytes(raw)).decode("ascii")
# request_hash intentionally left as-is → mismatch on decode-then-hash.

with open(dst, "w") as f:
    json.dump(rec, f, indent=2)
PY

rc_003=0
out_003="$(python3 "$REPLAY" "$ROOT/LOGS/t-replay-003-tampered.record.json" 2>&1)" || rc_003=$?
check_exit      "T-REPLAY-003 exit 2 (fail-closed)"     "$rc_003" "2"
assert_contains "T-REPLAY-003 hash mismatch message"    "$out_003" "request_hash mismatch"

echo

# ---------------------------------------------------------------------------
# T-REPLAY-004: Registry drift detection (future work — skipped)
# Requires a GOV_CAP_REGISTRY_PATH env override or controlled filesystem overlay
# to swap capability-registry.json at replay time without mutating the working tree.
# When implemented, replay should detect cap_registry_hash mismatch and exit 1.
# ---------------------------------------------------------------------------
echo "--- T-REPLAY-004: registry drift (skipped — future work) ---"
echo "SKIP: T-REPLAY-004 requires replay-time registry swap support"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
