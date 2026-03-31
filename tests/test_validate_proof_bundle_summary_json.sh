#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task157-validate-summary-json.XXXXXX")"
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

echo "--- T-VALIDATE-SUMMARY-JSON-001: validator summary JSON deterministic across two runs ---"
run_release_gate run1
bundle="$TMPDIR_LOCAL/out/proof-bundles/run1"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle" --summary-json "$TMPDIR_LOCAL/summary1.json" > "$TMPDIR_LOCAL/validate1.out"
bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$bundle" --summary-json "$TMPDIR_LOCAL/summary2.json" > "$TMPDIR_LOCAL/validate2.out"

grep -q 'SUMMARY_JSON_PATH=' "$TMPDIR_LOCAL/validate1.out"
J1="$(sha256_file "$TMPDIR_LOCAL/summary1.json")"
J2="$(sha256_file "$TMPDIR_LOCAL/summary2.json")"
[[ "$J1" == "$J2" ]] || { echo "FAIL: summary json nondeterministic"; exit 1; }
python3 - <<'PY' "$TMPDIR_LOCAL/summary1.json"
import json,sys
j=json.load(open(sys.argv[1], encoding='utf-8'))
assert j["report_version"] == "validate_proof_bundle_summary_v1"
assert j["proof_packet_version"] == "proof_packet_v1"
assert j["packet_hash"]["algo"] == "sha256"
assert j["summary_hash"]["algo"] == "sha256"
assert "queue_drift_scan" in j and "status_bundle" in j
print("PASS: summary json required keys/schema version present")
PY
echo "VALIDATE_SUMMARY_JSON_SHA256_RUN1=$J1"
echo "VALIDATE_SUMMARY_JSON_SHA256_RUN2=$J2"
echo "PASS: validator summary JSON deterministic across two runs"

