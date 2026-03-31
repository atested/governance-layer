#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task154-validate-proof-bundle.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_release_gate_fixture() {
  local run_id="$1"
  GOV_PROFILE=dev \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_RUN_ID="$run_id" \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/release-gate-$run_id.out"
}

echo "--- T-EXT-BUNDLE-VALIDATE-001: valid proof-bundle passes and validator output is deterministic ---"
run_release_gate_fixture fixed-run
bundle_dir="$TMPDIR_LOCAL/out/proof-bundles/fixed-run"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle_dir" > "$TMPDIR_LOCAL/validate1.out"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle_dir" > "$TMPDIR_LOCAL/validate2.out"

grep -q 'PASS: proof-bundle external contract valid' "$TMPDIR_LOCAL/validate1.out"
grep -q 'SUMMARY_REPORT_VERSION=proof_packet_verify_summary_v1' "$TMPDIR_LOCAL/validate1.out"
grep -q 'MANIFEST_PROOF_PACKET_VERSION=proof_packet_v1' "$TMPDIR_LOCAL/validate1.out"
D1="$(sha256_file "$TMPDIR_LOCAL/validate1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/validate2.out")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: validator output nondeterministic"; exit 1; }
echo "VALIDATOR_SHA256_RUN1=$D1"
echo "VALIDATOR_SHA256_RUN2=$D2"
echo "PASS: validator output deterministic across two runs"

echo
echo "--- T-EXT-BUNDLE-VALIDATE-002: missing required file fails with stable marker ---"
cp -R "$bundle_dir" "$TMPDIR_LOCAL/bad-bundle"
rm -f "$TMPDIR_LOCAL/bad-bundle/proof_packet_verify_summary.json"
set +e
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$TMPDIR_LOCAL/bad-bundle" > "$TMPDIR_LOCAL/bad.out" 2>&1
rc=$?
set -e
[[ "$rc" == "1" ]] || { echo "FAIL: expected validator rc=1 got $rc"; exit 1; }
grep -q 'FAIL: missing required file: proof_packet_verify_summary.json' "$TMPDIR_LOCAL/bad.out"
echo "PASS: missing required file negative control fails with stable marker (exit=$rc)"

