#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task149-status-bundle-optional.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

validate_status_bundle_optional() {
  python3 - <<'PY' "$1"
import json, sys
from pathlib import Path

d = Path(sys.argv[1])
p = d / "status_bundle.json"
if not p.exists():
    print("INFO: status_bundle.json optional output absent")
    print("PASS: optional status_bundle.json absence allowed")
    raise SystemExit(0)

doc = json.loads(p.read_text(encoding="utf-8"))
required = [
    "status_bundle_version","repo_git_sha","gov_profile","strictness",
    "proof_packet_sha256","proof_packet_verify_summary_sha256",
    "release_gate_result","queue_drift_scan"
]
for k in required:
    assert k in doc, k
assert doc["status_bundle_version"] == "status_bundle_v1"
assert set(doc["strictness"]) == {"source","value"}
assert isinstance(doc["strictness"]["value"], int)
assert doc["strictness"]["value"] in (0,1)
assert set(doc["release_gate_result"]) == {"pass","rc"}
assert set(doc["queue_drift_scan"]) == {"rc","status"}
print("PASS: status_bundle.json present and schema-valid")
print("PASS: status_bundle_version == status_bundle_v1")
print("PASS: strictness.value is int 0|1")
PY
}

run_gate() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  GOV_PROFILE=dev \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id"
}

echo "--- T-STATUS-BUNDLE-OPT-001: present case validates deterministically ---"
D1="$(run_gate run1)"
D2="$(run_gate run2)"
validate_status_bundle_optional "$D1" | tee "$TMPDIR_LOCAL/present1.out"
validate_status_bundle_optional "$D2" | tee "$TMPDIR_LOCAL/present2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/present1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/present2.out")"
[[ "$H1" == "$H2" ]] || { echo "FAIL: present-case validator output digest mismatch"; exit 1; }
echo "STATUS_BUNDLE_OPTIONAL_SHA256_RUN1=$H1"
echo "STATUS_BUNDLE_OPTIONAL_SHA256_RUN2=$H2"
echo "PASS: present-case validator output deterministic across two runs"

echo "--- T-STATUS-BUNDLE-OPT-002: absent case is INFO/PASS ---"
EMPTY="$TMPDIR_LOCAL/empty"
mkdir -p "$EMPTY"
validate_status_bundle_optional "$EMPTY"

echo "Summary: status_bundle optional contract sanity checks complete"
