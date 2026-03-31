#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task152-ci-gating-neg.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

BAD_FIXTURE="$TMPDIR_LOCAL/empty-fixture-root"
mkdir -p "$BAD_FIXTURE"

run_neg() {
  local out="$1"
  local rc_file="$2"
  set +e
  GOV_PROFILE=ci \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$BAD_FIXTURE" \
  bash "$ROOT/system/scripts/release-gate.sh" >"$out" 2>&1
  local rc=$?
  set -e
  printf '%s\n' "$rc" > "$rc_file"
}

echo "--- T-RELEASE-GATE-CI-NEG-001: ci profile fails closed when proof-packet fixture is unavailable ---"
run_neg "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/run1.rc"
run_neg "$TMPDIR_LOCAL/run2.out" "$TMPDIR_LOCAL/run2.rc"

RC1="$(cat "$TMPDIR_LOCAL/run1.rc")"
RC2="$(cat "$TMPDIR_LOCAL/run2.rc")"
[[ "$RC1" == "1" ]] || { echo "FAIL: expected run1 rc=1 got $RC1"; exit 1; }
[[ "$RC2" == "1" ]] || { echo "FAIL: expected run2 rc=1 got $RC2"; exit 1; }
grep -q 'INFO: proof-packet strictness source=profile GOV_PROFILE=ci value=1' "$TMPDIR_LOCAL/run1.out"
grep -q 'FAIL: proof-packet check required but unavailable reason=missing_fixture' "$TMPDIR_LOCAL/run1.out"
grep -q 'INFO: proof-packet strictness source=profile GOV_PROFILE=ci value=1' "$TMPDIR_LOCAL/run2.out"
grep -q 'FAIL: proof-packet check required but unavailable reason=missing_fixture' "$TMPDIR_LOCAL/run2.out"

D1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: negative-control output nondeterministic"; exit 1; }

echo "RC_RUN1=$RC1"
echo "RC_RUN2=$RC2"
echo "NEG_CTRL_SHA256_RUN1=$D1"
echo "NEG_CTRL_SHA256_RUN2=$D2"
echo "PASS: ci profile strict negative control produces deterministic failure output"

