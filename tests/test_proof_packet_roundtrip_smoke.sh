#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
ATTEST_BUNDLE="$ROOT/scripts/attest/bundle.py"
ATTEST_VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
POLICY_EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
CANON="$ROOT/tests/fixtures/canon_002a.json"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task131-proof-roundtrip.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_contains() {
  local name="$1" text="$2" needle="$3"
  [[ "$text" == *"$needle"* ]] || { echo "FAIL: $name (missing '$needle')"; exit 1; }
  echo "PASS: $name"
}

build_roundtrip_artifacts() {
  local prefix="$1"
  local rec="$2"
  local rpt="$3"
  local attest_input="$TMPDIR_LOCAL/${prefix}.attest_input"
  local att_bundle="$TMPDIR_LOCAL/${prefix}.attestation_bundle.tar"
  local pp="$TMPDIR_LOCAL/${prefix}.proof_packet.tar"
  local summary="$TMPDIR_LOCAL/${prefix}.verify.summary.json"

  cp -R "$FIX" "$attest_input"
  rm -f "$attest_input/replay_audit_report.json"

  python3 "$ATTEST_BUNDLE" pack --input-dir "$attest_input" --out "$att_bundle" >/tmp/${prefix}.attest_pack.log
  python3 "$ATTEST_VERIFY" "$att_bundle" >/tmp/${prefix}.attest_verify.log

  python3 "$PACKER" pack \
    --record "$rec" \
    --artifacts-dir "$FIX/artifacts" \
    --replay-audit-report "$rpt" \
    --out "$pp" >"/tmp/${prefix}.proof_pack.log"

  python3 "$PACKER" verify --bundle "$pp" --summary-json "$summary" >"/tmp/${prefix}.proof_verify.log"

  echo "$att_bundle|$pp|$summary"
}

echo "--- T-PROOF-ROUNDTRIP-001: roundtrip smoke passes + path contract checks ---"
SEED_REC="$TMPDIR_LOCAL/seed.record.json"
SEED_RPT="$TMPDIR_LOCAL/seed.replay_audit_report.json"
python3 "$POLICY_EVAL" "$CANON" > "$SEED_REC"
python3 "$REPLAY" --audit-report-json "$SEED_RPT" "$SEED_REC" >/tmp/replay.seed.log

IFS='|' read -r B1 PP1 SUM1 < <(build_roundtrip_artifacts run1 "$SEED_REC" "$SEED_RPT")
IFS='|' read -r B2 PP2 SUM2 < <(build_roundtrip_artifacts run2 "$SEED_REC" "$SEED_RPT")

PP_SHA1="$(sha256_file "$PP1")"
PP_SHA2="$(sha256_file "$PP2")"
SUM_SHA1="$(sha256_file "$SUM1")"
SUM_SHA2="$(sha256_file "$SUM2")"

[[ "$PP_SHA1" == "$PP_SHA2" ]] || { echo "FAIL: proof packet bytes nondeterministic"; exit 1; }
[[ "$SUM_SHA1" == "$SUM_SHA2" ]] || { echo "FAIL: proof packet verify summary nondeterministic"; exit 1; }
echo "PROOF_PACKET_SHA256_STABLE=yes"
echo "VERIFY_SUMMARY_SHA256_STABLE=yes"
echo "PASS: proof-packet roundtrip packet+summary digests deterministic across two runs"

ATT_VERIFY1="$(cat /tmp/run1.attest_verify.log)"
PROOF_VERIFY1="$(cat /tmp/run1.proof_verify.log)"
REPLAY_OUT1="$(cat /tmp/replay.seed.log)"
assert_contains "attestation bundle verify pass" "$ATT_VERIFY1" "PASS: attestation bundle manifest + payload hashes verified"
assert_contains "proof-packet verify pass" "$PROOF_VERIFY1" "PASS: proof packet manifest + payload hashes verified"
assert_contains "proof-packet verify machine contract" "$PROOF_VERIFY1" "PROOF_PACKET_VERIFY ok=yes reason=OK "
assert_contains "proof-packet verify summary contract" "$PROOF_VERIFY1" " summary_report_version=proof_packet_verify_summary_v2 "

python3 - <<'PY' "$PP1" "$SEED_RPT"
import hashlib, json, sys, tarfile
pp, rpt = sys.argv[1:3]
with tarfile.open(pp, 'r:') as tf:
    names = tf.getnames()
    assert "payload/replay_audit_report.json" in names, names
    manifest = json.load(tf.extractfile("manifest.json"))
    files = manifest["files"]
    assert "replay_audit_report.json" in files, files.keys()
    assert "record.json" in files, files.keys()
    src = manifest["source_summary"]
    assert "replay_report_hash" in src, src
    assert "record_bytes_sha256" in src, src
    expect = "sha256:" + hashlib.sha256(open(rpt, "rb").read()).hexdigest()
    assert src["replay_report_hash"] == expect, (src["replay_report_hash"], expect)
    assert files["replay_audit_report.json"]["sha256"] == expect
    assert src["record_bytes_sha256"] == files["record.json"]["sha256"], (
        src["record_bytes_sha256"], files["record.json"]["sha256"]
    )
print("PASS: replay audit report path contract and manifest/source_summary hash linkage verified")
print("PASS: record_bytes_sha256 linkage matches manifest record.json hash")
PY

assert_contains "replay stdout deterministic mismatch marker absent on clean run" "$REPLAY_OUT1" "PASS: replay matches original"

echo
echo "Summary: proof-packet roundtrip smoke complete"
