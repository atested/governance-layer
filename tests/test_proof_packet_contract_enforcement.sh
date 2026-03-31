#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task142-contracts.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

summarize_run() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  GOV_PROFILE=dev \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"

  local d="$out_base/$run_id"
  python3 - <<'PY' "$d" > "$TMPDIR_LOCAL/$run_id.contract.json"
import hashlib, json, re, sys, tarfile
from pathlib import Path

d = Path(sys.argv[1])
sha_file = d / "proof_packet.sha256"
tar_path = d / "proof_packet.tar"
summary_path = d / "proof_packet_verify_summary.json"

sha_line = sha_file.read_text(encoding="utf-8").strip()
m = re.fullmatch(r"([0-9a-f]{64})\s\sproof_packet\.tar", sha_line)
assert m, f"sha file format invalid: {sha_line!r}"
sha_hex = m.group(1)
calc_hex = hashlib.sha256(tar_path.read_bytes()).hexdigest()
assert sha_hex == calc_hex, (sha_hex, calc_hex)

summary = json.loads(summary_path.read_text(encoding="utf-8"))
assert summary["report_version"] == "proof_packet_verify_summary_v2", summary.get("report_version")

with tarfile.open(tar_path, "r:") as tf:
    manifest = json.load(tf.extractfile("manifest.json"))
assert manifest["proof_packet_version"] == "proof_packet_v1", manifest.get("proof_packet_version")

out = {
    "manifest_proof_packet_version": manifest["proof_packet_version"],
    "proof_packet_sha256_file_hex": sha_hex,
    "proof_packet_sha256_matches_tar": True,
    "summary_report_version": summary["report_version"],
}
print(json.dumps(out, sort_keys=True, separators=(",", ":")))
PY
}

echo "--- T-CONTRACT-001: proof-packet manifest/summary/sha contracts enforced and deterministic ---"
summarize_run run1
summarize_run run2
C1="$TMPDIR_LOCAL/run1.contract.json"
C2="$TMPDIR_LOCAL/run2.contract.json"
H1="$(sha256_file "$C1")"
H2="$(sha256_file "$C2")"
[[ "$H1" == "$H2" ]] || { echo "FAIL: contract summary digest mismatch"; exit 1; }
echo "CONTRACT_SUMMARY_SHA256_RUN1=$H1"
echo "CONTRACT_SUMMARY_SHA256_RUN2=$H2"
echo "PASS: contract summary deterministic across two runs"
grep -q '\"manifest_proof_packet_version\":\"proof_packet_v1\"' "$C1"
grep -q '\"summary_report_version\":\"proof_packet_verify_summary_v2\"' "$C1"
grep -q '\"proof_packet_sha256_matches_tar\":true' "$C1"
echo "PASS: manifest version, summary report_version, and proof_packet.sha256 contract checks enforced"
