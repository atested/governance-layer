#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task129-proof-summary.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

make_inputs_with_signing() {
  local dir="$1"
  mkdir -p "$dir"
  python3 - <<'PY' "$ROOT" "$FIX/record.json" "$dir/record.json"
import importlib.util, json, sys
from pathlib import Path

root = Path(sys.argv[1])
src = Path(sys.argv[2])
dst = Path(sys.argv[3])

verify_spec = importlib.util.spec_from_file_location("verify_record_impl", root / "scripts" / "verify-record.py")
verify_mod = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verify_mod)

doc = json.loads(src.read_text(encoding="utf-8"))
doc["signing_key_id"] = "ed25519:ci-summary-test"
doc["record_hash"] = "sha256:" + verify_mod.sha256_hex(verify_mod.signing_preimage_payload(doc))
doc["signature"] = None
dst.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
  cp "$FIX/replay_audit_report.json" "$dir/replay_audit_report.json"
  cp -R "$FIX/artifacts" "$dir/artifacts"
}

assert_canonical_summary_json() {
  python3 - <<'PY' "$1"
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
raw = p.read_text(encoding='utf-8')
assert raw.endswith('\n'), 'summary json must end with newline'
doc = json.loads(raw)
canonical = json.dumps(doc, sort_keys=True, separators=(',', ':')) + '\n'
assert raw == canonical, 'summary json must be canonical compact sorted-key JSON'
print('PASS: verifier summary JSON is canonical compact JSON with trailing newline')
PY
}

echo "--- T-PROOF-SUMMARY-001: verifier summary JSON deterministic across two runs ---"
BASE="$TMPDIR_LOCAL/base"
make_inputs_with_signing "$BASE"
PACKET="$TMPDIR_LOCAL/proof_packet.tar"

python3 "$PACKER" pack \
  --record "$BASE/record.json" \
  --artifacts-dir "$BASE/artifacts" \
  --replay-audit-report "$BASE/replay_audit_report.json" \
  --out "$PACKET" > "$TMPDIR_LOCAL/pack.log"

OUT1="$(python3 "$PACKER" verify --bundle "$PACKET" --summary-json "$TMPDIR_LOCAL/summary1.json")"
OUT2="$(python3 "$PACKER" verify --bundle "$PACKET" --summary-json "$TMPDIR_LOCAL/summary2.json")"

S1_SHA="$(sha256_file "$TMPDIR_LOCAL/summary1.json")"
S2_SHA="$(sha256_file "$TMPDIR_LOCAL/summary2.json")"
O1_SHA="$(python3 - <<'PY' "$OUT1"
import hashlib,sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
PY
)"
O2_SHA="$(python3 - <<'PY' "$OUT2"
import hashlib,sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
PY
)"
echo "VERIFY_SUMMARY_JSON_SHA256_RUN1=$S1_SHA"
echo "VERIFY_SUMMARY_JSON_SHA256_RUN2=$S2_SHA"
[[ "$S1_SHA" == "$S2_SHA" ]] || { echo "FAIL: verifier summary JSON digest mismatch"; exit 1; }
echo "VERIFY_STDOUT_SHA256_RUN1=$O1_SHA"
echo "VERIFY_STDOUT_SHA256_RUN2=$O2_SHA"
[[ "$O1_SHA" == "$O2_SHA" ]] || { echo "FAIL: verifier stdout digest mismatch"; exit 1; }
echo "PASS: verifier summary JSON deterministic across two runs"
assert_canonical_summary_json "$TMPDIR_LOCAL/summary1.json"

python3 - <<'PY' "$PACKET" "$TMPDIR_LOCAL/summary1.json"
import hashlib, json, sys
import io, tarfile
packet_path, summary_path = sys.argv[1:3]
summary = json.load(open(summary_path, "r", encoding="utf-8"))
required_top = ["report_version", "packet_hash", "counts", "strictness", "key_linkage"]
for k in required_top:
    assert k in summary, k
assert summary["report_version"] == "proof_packet_verify_summary_v2"
packet_hash = hashlib.sha256(open(packet_path, "rb").read()).hexdigest()
assert summary["packet_hash"] == {"algo": "sha256", "value": packet_hash}
with tarfile.open(packet_path, "r") as tf:
    manifest_bytes = tf.extractfile("manifest.json").read()
manifest_sha = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
assert summary["manifest_sha256"] == manifest_sha
assert summary["packet_id"] == "ppb_" + manifest_sha.split(":", 1)[1]
counts = summary["counts"]
for k in ["matched", "mismatched", "missing", "extra", "fatal"]:
    assert k in counts, k
assert counts["mismatched"] == 0 and counts["missing"] == 0 and counts["extra"] == 0 and counts["fatal"] == 0
link = summary["key_linkage"]
for k in ["replay_report_hash", "record_bytes_sha256", "record_hash", "signing_key_id"]:
    assert k in link, k
assert isinstance(link["record_bytes_sha256"], str) and link["record_bytes_sha256"].startswith("sha256:")
assert isinstance(link["replay_report_hash"], str) and link["replay_report_hash"].startswith("sha256:")
print("PASS: verifier summary JSON includes required keys, packet identity markers, counts, canonical packet_hash object, and key linkage fields")
print("SUMMARY_KEYS=" + ",".join(sorted(summary.keys())))
print("COUNTS=" + json.dumps(counts, sort_keys=True, separators=(',', ':')))
print("LINKAGE_KEYS=" + ",".join(sorted(link.keys())))
PY

python3 - <<'PY' "$TMPDIR_LOCAL/summary1.json"
import json, sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
gov = summary.get("governance_evidence")
assert gov is not None, "governance_evidence block missing"
assert gov["packet_id"] == summary["packet_id"]
assert gov["manifest_sha256"] == summary["manifest_sha256"]
link = summary["key_linkage"]
assert gov["record_bytes_sha256"] == link["record_bytes_sha256"]
assert gov["replay_report_hash"] == link["replay_report_hash"]
assert gov["result"] == summary["result"]
print("PASS: governance_evidence block mirrors summary identity + linkage fields")
assert gov.get("replay_outcome") == "pass", f"expected replay_outcome=pass, got {gov.get('replay_outcome')!r}"
print("PASS: governance_evidence.replay_outcome=pass for passing replay report")
PY

case "$OUT1" in
  *"PASS: proof packet manifest + payload hashes verified"*) echo "PASS: verify stdout pass marker present run1" ;;
  *) echo "FAIL: missing pass marker in run1"; exit 1 ;;
esac
case "$OUT1" in
  *"PROOF_PACKET_VERIFY ok=yes reason=OK "*) echo "PASS: verify machine contract present run1" ;;
  *) echo "FAIL: missing verify machine contract in run1"; exit 1 ;;
esac
case "$OUT1" in
  *" summary_report_version=proof_packet_verify_summary_v2 "*) echo "PASS: verify machine summary version present run1" ;;
  *) echo "FAIL: missing verify machine summary version in run1"; exit 1 ;;
esac
case "$OUT2" in
  *"PASS: proof packet manifest + payload hashes verified"*) echo "PASS: verify stdout pass marker present run2" ;;
  *) echo "FAIL: missing pass marker in run2"; exit 1 ;;
esac

echo "--- T-PROOF-SUMMARY-002: governance_evidence.replay_outcome=fail for failing replay report ---"
FAIL_REPLAY_DIR="$TMPDIR_LOCAL/fail_replay"
make_inputs_with_signing "$FAIL_REPLAY_DIR"
python3 - <<'PY' "$FAIL_REPLAY_DIR/replay_audit_report.json"
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
doc = json.loads(p.read_text(encoding="utf-8"))
doc["record_counts"]["mismatched"] = 1
p.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
FAIL_PACKET="$TMPDIR_LOCAL/fail_replay_packet.tar"
python3 "$PACKER" pack \
  --record "$FAIL_REPLAY_DIR/record.json" \
  --artifacts-dir "$FAIL_REPLAY_DIR/artifacts" \
  --replay-audit-report "$FAIL_REPLAY_DIR/replay_audit_report.json" \
  --out "$FAIL_PACKET" > "$TMPDIR_LOCAL/fail_pack.log"
python3 "$PACKER" verify --bundle "$FAIL_PACKET" --summary-json "$TMPDIR_LOCAL/fail_summary.json" > /dev/null
python3 - <<'PY' "$TMPDIR_LOCAL/fail_summary.json"
import json, sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
gov = summary.get("governance_evidence")
assert gov is not None, "governance_evidence block missing"
assert gov.get("replay_outcome") == "fail", f"expected fail, got {gov.get('replay_outcome')!r}"
print("PASS: governance_evidence.replay_outcome=fail for failing replay report")
PY

echo "--- T-PROOF-SUMMARY-003: governance_evidence.replay_outcome=unavailable for non-standard replay report ---"
UNAVAIL_REPLAY_DIR="$TMPDIR_LOCAL/unavail_replay"
make_inputs_with_signing "$UNAVAIL_REPLAY_DIR"
python3 - <<'PY' "$UNAVAIL_REPLAY_DIR/replay_audit_report.json"
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
doc = json.loads(p.read_text(encoding="utf-8"))
doc["report_version"] = "unknown_report_version_v99"
p.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
UNAVAIL_PACKET="$TMPDIR_LOCAL/unavail_packet.tar"
python3 "$PACKER" pack \
  --record "$UNAVAIL_REPLAY_DIR/record.json" \
  --artifacts-dir "$UNAVAIL_REPLAY_DIR/artifacts" \
  --replay-audit-report "$UNAVAIL_REPLAY_DIR/replay_audit_report.json" \
  --out "$UNAVAIL_PACKET" > "$TMPDIR_LOCAL/unavail_pack.log"
python3 "$PACKER" verify --bundle "$UNAVAIL_PACKET" --summary-json "$TMPDIR_LOCAL/unavail_summary.json" > /dev/null
python3 - <<'PY' "$TMPDIR_LOCAL/unavail_summary.json"
import json, sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
gov = summary.get("governance_evidence")
assert gov is not None, "governance_evidence block missing"
assert gov.get("replay_outcome") == "unavailable", f"expected unavailable, got {gov.get('replay_outcome')!r}"
print("PASS: governance_evidence.replay_outcome=unavailable for non-standard replay report version")
PY

echo
echo "Summary: proof-packet verifier summary JSON checks complete"
