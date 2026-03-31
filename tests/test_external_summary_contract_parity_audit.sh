#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/ext-summary-parity.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

OUT_BASE="$TMPDIR_LOCAL/out"
RUN_ID="task413_summary_parity"

(
  cd "$ROOT"
  GOV_PROFILE=dev \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$OUT_BASE/proof-bundles" \
  RELEASE_GATE_RUN_ID="$RUN_ID" \
  bash system/scripts/release-gate.sh >/dev/null
)

BUNDLE_DIR="$OUT_BASE/proof-bundles/$RUN_ID"
VALIDATE_SUMMARY="$BUNDLE_DIR/validate_proof_bundle_summary.json"

bash "$ROOT/system/scripts/validate-proof-bundle.sh" "$BUNDLE_DIR" --summary-json "$VALIDATE_SUMMARY" >/dev/null

python3 - <<'PY' "$ROOT/docs/EXTERNAL_CONTRACTS.md" "$ROOT/docs/DISTRIBUTION.md" "$BUNDLE_DIR/proof_packet_verify_summary.json" "$VALIDATE_SUMMARY"
import json
import sys
from pathlib import Path

external = Path(sys.argv[1]).read_text(encoding="utf-8")
distribution = Path(sys.argv[2]).read_text(encoding="utf-8")
proof = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
validate = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))

assert "proof_packet_verify_summary_v2" in external
assert "validate_proof_bundle_summary_v1" in external
assert "validate_proof_bundle_summary.json" in external
assert "validate_proof_bundle_summary.json" in distribution
assert "proof_packet_verify_summary_v2" in distribution
assert "validate_proof_bundle_summary_v1" in distribution

proof_required = [
    "report_version",
    "result",
    "packet_hash",
    "manifest_sha256",
    "packet_id",
    "counts",
    "strictness",
    "key_linkage",
]
validate_required = [
    "report_version",
    "result",
    "exit_code",
    "bundle_dir_basename",
    "packet_hash",
    "summary_hash",
    "counts",
    "queue_drift_scan_json_present",
    "status_bundle_present",
]
for key in proof_required:
    assert key in proof, key
for key in validate_required:
    assert key in validate, key
assert proof["report_version"] == "proof_packet_verify_summary_v2"
assert validate["report_version"] == "validate_proof_bundle_summary_v1"

print("PASS: external summary-contract parity surfaces align on current main")
PY
