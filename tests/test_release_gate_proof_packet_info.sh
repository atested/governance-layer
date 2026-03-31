#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RG="$ROOT/system/scripts/release-gate.sh"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task128-release-gate-proof.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_contains() {
  local name="$1" hay="$2" needle="$3"
  [[ "$hay" == *"$needle"* ]] || { echo "FAIL: $name (missing '$needle')"; exit 1; }
  echo "PASS: $name"
}

run_default_info() {
  local out_file="$1"
  RELEASE_GATE_SKIP_BASE=1 bash "$RG" > "$out_file"
}

echo "--- T-RELEASE-GATE-PROOF-001: default informational proof-packet section deterministic across two runs ---"
run_default_info "$TMPDIR_LOCAL/default1.out"
run_default_info "$TMPDIR_LOCAL/default2.out"
SHA1="$(sha256_file "$TMPDIR_LOCAL/default1.out")"
SHA2="$(sha256_file "$TMPDIR_LOCAL/default2.out")"
echo "RELEASE_GATE_PROOF_SECTION_SHA256_RUN1=$SHA1"
echo "RELEASE_GATE_PROOF_SECTION_SHA256_RUN2=$SHA2"
[[ "$SHA1" == "$SHA2" ]] || { echo "FAIL: release-gate proof section nondeterministic"; exit 1; }
echo "PASS: release-gate proof-packet section deterministic across two runs"
OUT_DEFAULT="$(cat "$TMPDIR_LOCAL/default1.out")"
assert_contains "default includes proof-packet header" "$OUT_DEFAULT" "## Proof-Packet Check (informational)"
assert_contains "default is informational strict=0" "$OUT_DEFAULT" "INFO: proof-packet strict=0"
assert_contains "default prints pass marker" "$OUT_DEFAULT" "INFO: proof-packet check pass packet_sha="

echo
echo "--- T-RELEASE-GATE-PROOF-002: strict mode pass when proof-packet check succeeds ---"
STRICT_OK_OUT="$(RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_STRICT_PROOF_PACKET=1 bash "$RG")"
assert_contains "strict mode line" "$STRICT_OK_OUT" "INFO: proof-packet strict=1"
assert_contains "strict pass marker" "$STRICT_OK_OUT" "INFO: proof-packet check pass packet_sha="
echo "PASS: strict proof-packet mode passes when check succeeds"

echo
echo "--- T-RELEASE-GATE-PROOF-003: strict mode fails deterministically when fixture unavailable ---"
set +e
STRICT_FAIL_OUT="$(RELEASE_GATE_SKIP_BASE=1 RELEASE_GATE_STRICT_PROOF_PACKET=1 RELEASE_GATE_PROOF_PACKET_FIXTURE_ROOT="$TMPDIR_LOCAL/missing-fixture" bash "$RG" 2>&1)"
STRICT_FAIL_RC=$?
set -e
[[ "$STRICT_FAIL_RC" != "0" ]] || { echo "FAIL: strict missing-fixture mode unexpectedly passed"; exit 1; }
assert_contains "strict fail marker" "$STRICT_FAIL_OUT" "FAIL: proof-packet check required but unavailable reason=missing_fixture"
echo "PASS: strict proof-packet mode fails deterministically when fixture unavailable (rc=$STRICT_FAIL_RC)"

echo
echo "Summary: release-gate informational proof-packet check tests complete"
