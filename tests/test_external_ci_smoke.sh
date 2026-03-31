#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task151-external-ci-smoke.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

assert_bundle_contract() {
  python3 - <<'PY' "$1" > "$2"
import hashlib, json, re, sys
from pathlib import Path

d = Path(sys.argv[1])
required = ["proof_packet.tar","proof_packet.sha256","proof_packet_verify_summary.json","release_gate_log.txt","versions.txt"]
for name in required:
    if not (d / name).is_file():
        raise SystemExit(f"FAIL: missing required file: {name}")
sha_line = (d / "proof_packet.sha256").read_text(encoding="utf-8").strip()
m = re.fullmatch(r"([0-9a-f]{64})\s\sproof_packet\.tar", sha_line)
if not m:
    raise SystemExit("FAIL: invalid proof_packet.sha256 format")
packet_hex = hashlib.sha256((d / "proof_packet.tar").read_bytes()).hexdigest()
if packet_hex != m.group(1):
    raise SystemExit("FAIL: proof_packet.sha256 checksum mismatch")
summary = json.loads((d / "proof_packet_verify_summary.json").read_text(encoding="utf-8"))
if summary.get("report_version") != "proof_packet_verify_summary_v2":
    raise SystemExit("FAIL: summary report_version mismatch")
out = {
    "proof_packet_sha256": packet_hex,
    "summary_report_version": summary["report_version"],
}
print(json.dumps(out, sort_keys=True, separators=(",", ":")))
PY
}

echo "--- T-EXTERNAL-CI-SMOKE-001: bootstrap dry-run + release-gate + core contract assertions ---"

# Non-destructive bootstrap command smoke
BOOTSTRAP_RELEASE_GATE_SKIP_BASE=1 bash "$ROOT/system/scripts/bootstrap-run.sh" --dry-run > "$TMPDIR_LOCAL/bootstrap.out"
grep -q '^BOOTSTRAP_EXPECTED_OUTPUT_DIR=out/proof-bundles/<run-id>/$' "$TMPDIR_LOCAL/bootstrap.out"
echo "PASS: bootstrap-run dry-run reports expected proof-bundle output location"

run_gate() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  GOV_PROFILE=ci \
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id"
}

D1="$(run_gate run1)"
D2="$(run_gate run2)"
assert_bundle_contract "$D1" "$TMPDIR_LOCAL/run1.contract.json"
assert_bundle_contract "$D2" "$TMPDIR_LOCAL/run2.contract.json"
C1="$(sha256_file "$TMPDIR_LOCAL/run1.contract.json")"
C2="$(sha256_file "$TMPDIR_LOCAL/run2.contract.json")"
[[ "$C1" == "$C2" ]] || { echo "FAIL: external CI smoke contract digest mismatch"; exit 1; }
echo "EXTERNAL_CI_SMOKE_SHA256_RUN1=$C1"
echo "EXTERNAL_CI_SMOKE_SHA256_RUN2=$C2"
echo "PASS: external CI smoke contract digest deterministic across two runs"
echo "PASS: proof-bundle required files exist and summary report_version is proof_packet_verify_summary_v2"

echo "Summary: external CI single-command smoke checks complete"
