#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task141-status-bundle.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_once() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  GOV_PROFILE=dev \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id/status_bundle.json"
}

echo "--- T-STATUS-BUNDLE-001: deterministic status_bundle.json across two runs ---"
S1="$(run_once run1)"
S2="$(run_once run2)"
H1="$(sha256_file "$S1")"
H2="$(sha256_file "$S2")"
[[ "$H1" == "$H2" ]] || { echo "FAIL: status bundle digest mismatch"; exit 1; }
echo "STATUS_BUNDLE_SHA256_RUN1=$H1"
echo "STATUS_BUNDLE_SHA256_RUN2=$H2"

python3 - <<'PY' "$S1"
import json,sys
doc=json.load(open(sys.argv[1], 'r', encoding='utf-8'))
for k in ["status_bundle_version","repo_git_sha","gov_profile","strictness","proof_packet_sha256","proof_packet_verify_summary_sha256","release_gate_result","queue_drift_scan"]:
    assert k in doc, k
assert doc["status_bundle_version"] == "status_bundle_v1"
assert set(doc["strictness"].keys()) == {"source","value"}
assert isinstance(doc["strictness"]["value"], int), type(doc["strictness"]["value"]).__name__
assert set(doc["release_gate_result"].keys()) == {"pass","rc"}
assert set(doc["queue_drift_scan"].keys()) == {"rc","status"}
assert doc["gov_profile"] == "dev"
print("PASS: status_bundle.json required keys present")
print("PASS: status_bundle.json structure matches contract")
print("PASS: status_bundle_version == status_bundle_v1")
print("PASS: strictness.value is integer typed")
PY

echo "Summary: status bundle json determinism checks complete"
