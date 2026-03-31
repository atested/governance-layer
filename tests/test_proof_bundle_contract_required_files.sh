#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task148-proof-bundle-contract.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

validate_dir() {
  python3 - <<'PY' "$1"
import hashlib, re, sys
from pathlib import Path

d = Path(sys.argv[1])
required = [
    "proof_packet.tar",
    "proof_packet.sha256",
    "proof_packet_verify_summary.json",
    "release_gate_log.txt",
    "versions.txt",
]
for name in required:
    p = d / name
    if not p.is_file():
        raise SystemExit(f"FAIL: missing required file: {name}")
sha_line = (d / "proof_packet.sha256").read_text(encoding="utf-8").strip()
m = re.fullmatch(r"([0-9a-f]{64})\s\sproof_packet\.tar", sha_line)
if not m:
    raise SystemExit("FAIL: invalid proof_packet.sha256 format")
calc = hashlib.sha256((d / "proof_packet.tar").read_bytes()).hexdigest()
if calc != m.group(1):
    raise SystemExit("FAIL: proof_packet.sha256 checksum mismatch")
print("PASS: required proof-bundle files present")
print("PASS: proof_packet.sha256 format valid")
print("PASS: proof_packet.sha256 matches proof_packet.tar bytes")
PY
}

run_gate() {
  local run_id="$1"
  local out_base="$TMPDIR_LOCAL/out"
  RELEASE_GATE_SKIP_BASE=1 \
  GOV_PROFILE=ci \
  RELEASE_GATE_PROOF_BUNDLE_OUT_BASE="$out_base" \
  RELEASE_GATE_RUN_ID="$run_id" \
  bash "$ROOT/system/scripts/release-gate.sh" > "$TMPDIR_LOCAL/$run_id.release_gate.out"
  echo "$out_base/$run_id"
}

echo "--- T-PROOF-BUNDLE-CONTRACT-001: required files + checksum pass deterministically ---"
D1="$(run_gate run1)"
D2="$(run_gate run2)"
validate_dir "$D1" | tee "$TMPDIR_LOCAL/validate1.out"
validate_dir "$D2" | tee "$TMPDIR_LOCAL/validate2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/validate1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/validate2.out")"
[[ "$H1" == "$H2" ]] || { echo "FAIL: validator output digest mismatch"; exit 1; }
echo "VALIDATOR_OUT_SHA256_RUN1=$H1"
echo "VALIDATOR_OUT_SHA256_RUN2=$H2"
echo "PASS: validator output deterministic across two runs"

echo "--- T-PROOF-BUNDLE-CONTRACT-002: missing required file fails deterministically ---"
BAD="$TMPDIR_LOCAL/missing"
mkdir -p "$BAD"
cp "$D1"/proof_packet.tar "$BAD"/
cp "$D1"/proof_packet.sha256 "$BAD"/
set +e
validate_dir "$BAD" > "$TMPDIR_LOCAL/missing.out" 2>&1
RC=$?
set -e
[[ "$RC" -ne 0 ]] || { echo "FAIL: missing-file negative control unexpectedly passed"; exit 1; }
grep -q '^FAIL: missing required file: proof_packet_verify_summary.json' "$TMPDIR_LOCAL/missing.out"
cat "$TMPDIR_LOCAL/missing.out"
echo "PASS: missing required file negative control fails with stable marker (exit=$RC)"

echo "Summary: proof-bundle required-files contract checks complete"
