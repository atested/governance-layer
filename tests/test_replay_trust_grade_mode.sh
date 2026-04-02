#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIXTURE="$ROOT/tests/fixtures/canon_001a.json"
TEST_KEY_FILE="$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/gov-replay-trust.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

pass=0
fail=0

check_exit() {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_contains() {
  local name="$1" file="$2" needle="$3"
  if grep -Fq "$needle" "$file"; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  expected to find: $needle"
    echo "  output:"
    sed 's/^/    /' "$file"
    fail=$((fail+1))
  fi
}

run_capture() {
  local outfile="$1"
  shift
  set +e
  "$@" >"$outfile" 2>&1
  local rc=$?
  set -e
  return "$rc"
}

mk_signing_pair() {
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

KEY_PATH="$tmpdir/signing.key"
PUB_PATH="$tmpdir/verify.pub"
mk_signing_pair "$KEY_PATH" "$PUB_PATH"

python3 "$EVAL" "$FIXTURE" >"$tmpdir/unsigned.json"
env GOV_SIGNING_KEY_PATH="$KEY_PATH" python3 "$EVAL" "$FIXTURE" >"$tmpdir/signed.json"

echo "--- T-REPLAY-TRUST-001: trust-grade replay accepts signed record ---"
out="$tmpdir/t1.out"
rc=0
run_capture "$out" env GOV_SIGNING_REQUIRED=1 GOV_SIGNING_KEY_PATH="$KEY_PATH" GOV_VERIFY_KEY_PATH="$PUB_PATH" python3 "$REPLAY" "$tmpdir/signed.json" || rc=$?
check_exit "T-REPLAY-TRUST-001 signed trust-grade replay" "$rc" "0"
assert_contains "T-REPLAY-TRUST-001 output" "$out" "PASS: replay matches original"

echo
echo "--- T-REPLAY-TRUST-002: trust-grade replay rejects unsigned original record ---"
out="$tmpdir/t2.out"
rc=0
run_capture "$out" env GOV_SIGNING_REQUIRED=1 GOV_VERIFY_KEY_PATH="$PUB_PATH" python3 "$REPLAY" "$tmpdir/unsigned.json" || rc=$?
check_exit "T-REPLAY-TRUST-002 unsigned baseline rejected" "$rc" "1"
assert_contains "T-REPLAY-TRUST-002 output" "$out" "FAIL: unsigned record rejected in GOV_SIGNING_REQUIRED=1 mode"

echo
echo "--- T-REPLAY-TRUST-003: trust-grade replay fails closed if replay output cannot be signed ---"
out="$tmpdir/t3.out"
rc=0
run_capture "$out" env GOV_SIGNING_REQUIRED=1 GOV_VERIFY_KEY_PATH="$PUB_PATH" python3 "$REPLAY" "$tmpdir/signed.json" || rc=$?
check_exit "T-REPLAY-TRUST-003 missing replay signing key" "$rc" "2"
assert_contains "T-REPLAY-TRUST-003 output" "$out" "FATAL: signed PolicyRecord required for trust-grade mode"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
