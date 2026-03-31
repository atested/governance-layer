#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task160-qds-json.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

echo "--- T-QDS-JSON-OPT-001: queue_drift_scan.json emitted with deterministic schema/digest ---"
for run in run1 run2; do
  RELEASE_GATE_SKIP_BASE=1 GOV_PROFILE=dev RELEASE_GATE_RUN_ID="$run" RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$TMPDIR_LOCAL/out/proof-bundles" \
    bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run.out"
done

python3 - <<'PY' "$TMPDIR_LOCAL/out/proof-bundles/run1/queue_drift_scan.json" "$TMPDIR_LOCAL/out/proof-bundles/run1/queue_drift_scan.txt"
import json, hashlib, sys
j = json.load(open(sys.argv[1], encoding='utf-8'))
t = open(sys.argv[2], encoding='utf-8').read().encode('utf-8')
assert j["queue_drift_scan_version"] == "queue_drift_scan_v1"
assert j["status"] in ("present", "unavailable")
assert isinstance(j["rc"], int)
assert j["text_sha256"] == hashlib.sha256(t).hexdigest()
print("PASS: queue_drift_scan.json schema/version and text digest linkage valid")
PY
J1="$(sha256_file "$TMPDIR_LOCAL/out/proof-bundles/run1/queue_drift_scan.json")"
J2="$(sha256_file "$TMPDIR_LOCAL/out/proof-bundles/run2/queue_drift_scan.json")"
[[ "$J1" == "$J2" ]] || { echo "FAIL: queue_drift_scan.json nondeterministic"; exit 1; }
echo "QDS_JSON_SHA256_RUN1=$J1"
echo "QDS_JSON_SHA256_RUN2=$J2"
echo "PASS: queue_drift_scan.json deterministic across two runs"

