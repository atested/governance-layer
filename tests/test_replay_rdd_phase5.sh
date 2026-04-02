#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPLAY="$ROOT/scripts/replay-record.py"
FIX="$ROOT/tests/fixtures"
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"

pass=0
fail=0

pass_case () {
  local id="$1" msg="$2"
  echo "PASS: $id $msg"
  pass=$((pass+1))
}

fail_case () {
  local id="$1" msg="$2"
  echo "FAIL: $id $msg"
  fail=$((fail+1))
}

check_exit () {
  local id="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    pass_case "$id" "exit=$got"
  else
    fail_case "$id" "exit got=$got want=$want"
  fi
}

assert_contains () {
  local id="$1" text="$2" expect="$3"
  if echo "$text" | grep -Fq "$expect"; then
    pass_case "$id" "contains '$expect'"
  else
    fail_case "$id" "missing '$expect'"
    echo "$text"
  fi
}

mk_signing_pair () {
  local key_path="$1" pub_path="$2"
  cp "$TEST_KEY_FILE" "$key_path"
  python3 <<PY
from pathlib import Path
from cryptography.hazmat.primitives import serialization
key = Path("$key_path")
priv = serialization.load_pem_private_key(key.read_bytes(), password=None)
pub = priv.public_key()
Path("$pub_path").write_bytes(pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
))
PY
}

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-replay-phase5.XXXXXX")"
cleanup(){ rm -rf "$TMPDIR_LOCAL"; }
trap cleanup EXIT

KEY_PATH="$TMPDIR_LOCAL/key.pem"
PUB_PATH="$TMPDIR_LOCAL/key.pub.pem"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"
export GOV_SIGNING_KEY_PATH="$KEY_PATH"
export GOV_VERIFY_KEY_PATH="$PUB_PATH"

# T-RDD-REPLAY-001: triage replay positive
out_001="$(python3 "$REPLAY" "$FIX/rdd_phase5_replay_valid_triage.json" 2>&1)"
rc_001=$?
check_exit "T-RDD-REPLAY-001" "$rc_001" "0"
assert_contains "T-RDD-REPLAY-001A" "$out_001" "PASS: replay matches original"
assert_contains "T-RDD-REPLAY-001B" "$out_001" "RECORDS_SHA="

# T-RDD-REPLAY-002: terminal replay positive
out_002="$(python3 "$REPLAY" "$FIX/rdd_phase5_replay_valid_terminal.json" 2>&1)"
rc_002=$?
check_exit "T-RDD-REPLAY-002" "$rc_002" "0"
assert_contains "T-RDD-REPLAY-002A" "$out_002" "PASS: replay matches original"
assert_contains "T-RDD-REPLAY-002B" "$out_002" "RECORDS_SHA="

# T-RDD-REPLAY-003: triage missing originating field fails closed
set +e
out_003="$(python3 "$REPLAY" "$FIX/rdd_phase5_replay_missing_originating_field.json" 2>&1)"
rc_003=$?
set -e
check_exit "T-RDD-REPLAY-003" "$rc_003" "1"
assert_contains "T-RDD-REPLAY-003A" "$out_003" "missing required field originating_pass_hash"

# T-RDD-REPLAY-004: unsupported record type fails closed
set +e
out_004="$(python3 "$REPLAY" "$FIX/rdd_phase5_replay_unsupported_record_type.json" 2>&1)"
rc_004=$?
set -e
check_exit "T-RDD-REPLAY-004" "$rc_004" "2"
assert_contains "T-RDD-REPLAY-004A" "$out_004" "unsupported record_type"

# T-RDD-REPLAY-005: deterministic output hash for positive matrix
run1="$(mktemp "${TMPDIR:-/tmp}/rdd-replay-p5-run1.XXXXXX")"
run2="$(mktemp "${TMPDIR:-/tmp}/rdd-replay-p5-run2.XXXXXX")"
python3 "$REPLAY" "$FIX/rdd_phase5_replay_valid_triage.json" "$FIX/rdd_phase5_replay_valid_terminal.json" > "$run1" 2>&1
python3 "$REPLAY" "$FIX/rdd_phase5_replay_valid_triage.json" "$FIX/rdd_phase5_replay_valid_terminal.json" > "$run2" 2>&1
h1="$(sha256sum "$run1" | awk '{print $1}')"
h2="$(sha256sum "$run2" | awk '{print $1}')"
echo "DETERMINISM_RUN1_HASH=$h1"
echo "DETERMINISM_RUN2_HASH=$h2"
if [[ "$h1" == "$h2" ]]; then
  pass_case "T-RDD-REPLAY-005" "deterministic matrix output"
else
  fail_case "T-RDD-REPLAY-005" "determinism hash mismatch"
fi
rm -f "$run1" "$run2"

echo "PASS: $pass  FAIL: $fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
