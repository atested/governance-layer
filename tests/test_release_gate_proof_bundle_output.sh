#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task136-proof-bundle-out.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

run_gate() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id"
}

echo "--- T-RELEASE-GATE-BUNDLE-001: emits deterministic proof-bundle output contract ---"
OD1="$(run_gate run1)"
OD2="$(run_gate run2)"
for d in "$OD1" "$OD2"; do
  test -f "$d/proof_packet.tar"
  test -f "$d/proof_packet.sha256"
  test -f "$d/proof_packet_verify_summary.json"
  test -f "$d/release_gate_log.txt"
  test -f "$d/versions.txt"
  test -f "$d/queue_drift_scan.txt"
done

P1="$(sha256_file "$OD1/proof_packet.tar")"
P2="$(sha256_file "$OD2/proof_packet.tar")"
S1="$(sha256_file "$OD1/proof_packet_verify_summary.json")"
S2="$(sha256_file "$OD2/proof_packet_verify_summary.json")"
[[ "$P1" == "$P2" ]] || { echo "FAIL: proof_packet.tar sha mismatch"; exit 1; }
[[ "$S1" == "$S2" ]] || { echo "FAIL: summary json sha mismatch"; exit 1; }
echo "PROOF_PACKET_SHA256_RUN1=$P1"
echo "PROOF_PACKET_SHA256_RUN2=$P2"
echo "PROOF_PACKET_SUMMARY_SHA256_RUN1=$S1"
echo "PROOF_PACKET_SUMMARY_SHA256_RUN2=$S2"
echo "PASS: proof packet and summary hashes stable across runs"

L1="$(cd "$OD1" && ls -1 | sort | paste -sd, -)"
L2="$(cd "$OD2" && ls -1 | sort | paste -sd, -)"
[[ "$L1" == "$L2" ]] || { echo "FAIL: bundle file list mismatch"; exit 1; }
echo "BUNDLE_FILES=$L1"
echo "PASS: proof-bundle directory contains expected files"

