#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task177-summary-contract.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_release_gate() {
  local run_id="$1"
  GOV_PROFILE=dev \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_RUN_ID="$run_id" \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
}

check_summary_json() {
  local path="$1" expected_result="$2" expected_exit="$3"
  python3 - <<'PY' "$path" "$expected_result" "$expected_exit"
import json, sys
j=json.load(open(sys.argv[1], encoding='utf-8'))
assert j["report_version"] == "validate_proof_bundle_summary_v1"
assert j["result"] == sys.argv[2]
assert j["exit_code"] == int(sys.argv[3])
assert isinstance(j["counts"], dict)
assert isinstance(j["queue_drift_scan_json_present"], bool)
assert isinstance(j["status_bundle_present"], bool)
assert isinstance(j["packet_hash"], dict) and j["packet_hash"]["algo"] == "sha256"
assert isinstance(j["summary_hash"], dict) and j["summary_hash"]["algo"] == "sha256"
print("PASS: summary json contract keys/types/schema version present")
PY
}

echo "--- T-VALIDATE-SUMMARY-CONTRACT-001: PASS summary json deterministic across two runs ---"
run_release_gate run1
bundle="$TMPDIR_LOCAL/out/proof-bundles/run1"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle" --summary-json "$TMPDIR_LOCAL/pass1.json" > "$TMPDIR_LOCAL/pass1.out"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle" --summary-json "$TMPDIR_LOCAL/pass2.json" > "$TMPDIR_LOCAL/pass2.out"
grep -q 'SUMMARY_JSON_PATH=' "$TMPDIR_LOCAL/pass1.out"
grep -q 'SUMMARY_JSON_PATH=' "$TMPDIR_LOCAL/pass2.out"
check_summary_json "$TMPDIR_LOCAL/pass1.json" PASS 0
P1="$(sha256_file "$TMPDIR_LOCAL/pass1.json")"
P2="$(sha256_file "$TMPDIR_LOCAL/pass2.json")"
echo "PASS_JSON_SHA256_RUN1=$P1"
echo "PASS_JSON_SHA256_RUN2=$P2"
[[ "$P1" == "$P2" ]] || { echo "FAIL: PASS summary json nondeterministic"; exit 1; }
echo "PASS: PASS summary json deterministic across two runs"

echo "--- T-VALIDATE-SUMMARY-CONTRACT-002: FAIL summary json deterministic across two runs ---"
mkdir -p "$TMPDIR_LOCAL/failrun1" "$TMPDIR_LOCAL/failrun2"
cp -R "$bundle" "$TMPDIR_LOCAL/failrun1/bundle"
cp -R "$bundle" "$TMPDIR_LOCAL/failrun2/bundle"
rm -f "$TMPDIR_LOCAL/failrun1/bundle/proof_packet_verify_summary.json"
rm -f "$TMPDIR_LOCAL/failrun2/bundle/proof_packet_verify_summary.json"
set +e
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$TMPDIR_LOCAL/failrun1/bundle" --summary-json "$TMPDIR_LOCAL/fail1.json" > "$TMPDIR_LOCAL/fail1.out" 2>&1; rcf1=$?
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$TMPDIR_LOCAL/failrun2/bundle" --summary-json "$TMPDIR_LOCAL/fail2.json" > "$TMPDIR_LOCAL/fail2.out" 2>&1; rcf2=$?
set -e
echo "PASS: FAIL-path rc run1=$rcf1 run2=$rcf2"
[[ $rcf1 -eq 1 && $rcf2 -eq 1 ]] || { echo "FAIL: FAIL-path rc mismatch"; exit 1; }
grep -q 'FAIL: missing required file: proof_packet_verify_summary.json' "$TMPDIR_LOCAL/fail1.out"
grep -q 'FAIL: missing required file: proof_packet_verify_summary.json' "$TMPDIR_LOCAL/fail2.out"
check_summary_json "$TMPDIR_LOCAL/fail1.json" FAIL 1
F1="$(sha256_file "$TMPDIR_LOCAL/fail1.json")"
F2="$(sha256_file "$TMPDIR_LOCAL/fail2.json")"
echo "FAIL_JSON_SHA256_RUN1=$F1"
echo "FAIL_JSON_SHA256_RUN2=$F2"
[[ "$F1" == "$F2" ]] || { echo "FAIL: FAIL summary json nondeterministic"; exit 1; }
echo "PASS: FAIL summary json deterministic across two runs"

echo "--- T-VALIDATE-SUMMARY-CONTRACT-003: ERROR summary json deterministic across two runs ---"
set +e
bash "$ROOT/system/scripts/validate-proof-bundle.sh" --summary-json "$TMPDIR_LOCAL/err1.json" --not-a-real-flag > "$TMPDIR_LOCAL/err1.out" 2>&1; rce1=$?
bash "$ROOT/system/scripts/validate-proof-bundle.sh" --summary-json "$TMPDIR_LOCAL/err2.json" --not-a-real-flag > "$TMPDIR_LOCAL/err2.out" 2>&1; rce2=$?
set -e
echo "PASS: ERROR-path rc run1=$rce1 run2=$rce2"
[[ $rce1 -eq 2 && $rce2 -eq 2 ]] || { echo "FAIL: ERROR-path rc mismatch"; exit 1; }
grep -q 'ERROR: unknown arg: --not-a-real-flag' "$TMPDIR_LOCAL/err1.out"
grep -q 'ERROR: unknown arg: --not-a-real-flag' "$TMPDIR_LOCAL/err2.out"
check_summary_json "$TMPDIR_LOCAL/err1.json" ERROR 2
E1="$(sha256_file "$TMPDIR_LOCAL/err1.json")"
E2="$(sha256_file "$TMPDIR_LOCAL/err2.json")"
echo "ERROR_JSON_SHA256_RUN1=$E1"
echo "ERROR_JSON_SHA256_RUN2=$E2"
[[ "$E1" == "$E2" ]] || { echo "FAIL: ERROR summary json nondeterministic"; exit 1; }
echo "PASS: ERROR summary json deterministic across two runs"

echo "Summary: validator summary json contract enforcement tests complete"
