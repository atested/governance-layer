#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
POLICY_EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
CANON="$ROOT/tests/fixtures/canon_002a.json"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task133-proof-det.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_eq() {
  local name="$1" a="$2" b="$3"
  [[ "$a" == "$b" ]] || { echo "FAIL: $name ($a != $b)"; exit 1; }
  echo "PASS: $name"
}

assert_ne() {
  local name="$1" a="$2" b="$3"
  [[ "$a" != "$b" ]] || { echo "FAIL: $name ($a == $b)"; exit 1; }
  echo "PASS: $name"
}

seed_inputs() {
  local dir="$1"
  mkdir -p "$dir"
  python3 "$POLICY_EVAL" "$CANON" > "$dir/record.json"
  python3 "$REPLAY" --audit-report-json "$dir/replay_audit_report.json" "$dir/record.json" > "$dir/replay.stdout"
  cp -R "$FIX/artifacts" "$dir/artifacts"
}

pack_from() {
  local cwd="$1" name="$2" in_dir="$3"
  local out="$TMPDIR_LOCAL/${name}.proof_packet.tar"
  local sum="$TMPDIR_LOCAL/${name}.verify.summary.json"
  (
    cd "$cwd"
    python3 "$PACKER" pack \
      --record "$in_dir/record.json" \
      --artifacts-dir "$in_dir/artifacts" \
      --replay-audit-report "$in_dir/replay_audit_report.json" \
      --out "$out" > "$TMPDIR_LOCAL/${name}.pack.log"
    python3 "$PACKER" verify --bundle "$out" --summary-json "$sum" > "$TMPDIR_LOCAL/${name}.verify.log"
  )
  echo "$out|$sum"
}

members_csv() {
  python3 - <<'PY' "$1"
import sys, tarfile
with tarfile.open(sys.argv[1], "r:") as tf:
    print(",".join(tf.getnames()))
PY
}

expected_member_order() {
  python3 - <<'PY' "$1"
from pathlib import Path
import sys
art = Path(sys.argv[1]) / "artifacts"
payload = ["record.json", "replay_audit_report.json"]
for p in sorted(art.rglob("*")):
    if p.is_file():
        payload.append("artifacts/" + p.relative_to(art).as_posix())
members = ["manifest.json"] + [f"payload/{rel}" for rel in sorted(payload)]
print(",".join(members))
PY
}

echo "--- T-PROOF-DET-001: same inputs => identical packet bytes + verifier summary ---"
BASE="$TMPDIR_LOCAL/base"
seed_inputs "$BASE"
mkdir -p "$TMPDIR_LOCAL/cwd_a" "$TMPDIR_LOCAL/cwd_b"
IFS='|' read -r P1 S1 < <(pack_from "$TMPDIR_LOCAL/cwd_a" run1 "$BASE")
IFS='|' read -r P2 S2 < <(pack_from "$TMPDIR_LOCAL/cwd_b" run2 "$BASE")
P1_SHA="$(sha256_file "$P1")"
P2_SHA="$(sha256_file "$P2")"
S1_SHA="$(sha256_file "$S1")"
S2_SHA="$(sha256_file "$S2")"
echo "PROOF_PACKET_SHA256_STABLE=yes"
echo "VERIFY_SUMMARY_SHA256_STABLE=yes"
assert_eq "same inputs packet sha deterministic" "$P1_SHA" "$P2_SHA"
assert_eq "same inputs verifier summary sha deterministic" "$S1_SHA" "$S2_SHA"

echo
echo "--- T-PROOF-DET-002: tar member ordering stable and canonical ---"
M1="$(members_csv "$P1")"
M2="$(members_csv "$P2")"
EXP="$(expected_member_order "$BASE")"
echo "TAR_MEMBERS_RUN1=$M1"
echo "TAR_MEMBERS_RUN2=$M2"
echo "TAR_MEMBERS_EXPECTED=$EXP"
assert_eq "tar member listing stable across runs" "$M1" "$M2"
assert_eq "tar member listing matches canonical order" "$M1" "$EXP"

echo
echo "--- T-PROOF-DET-003: changed input => different packet hash (sanity) ---"
CHANGED="$TMPDIR_LOCAL/changed"
cp -R "$BASE" "$CHANGED"
printf 'request-body-tampered\n' > "$CHANGED/artifacts/request.txt"
IFS='|' read -r P3 S3 < <(pack_from "$TMPDIR_LOCAL/cwd_a" changed "$CHANGED")
P3_SHA="$(sha256_file "$P3")"
S3_SHA="$(sha256_file "$S3")"
echo "PROOF_PACKET_SHA256_CHANGED_INPUT_DETECTED=yes"
echo "VERIFY_SUMMARY_SHA256_CHANGED_INPUT_DETECTED=yes"
assert_ne "changed input changes packet sha" "$P1_SHA" "$P3_SHA"
echo "PASS: changed-input packet still verifies"

echo
echo "Summary: proof-packet determinism regression complete"
