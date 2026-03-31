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
packet_path, summary_path = sys.argv[1:3]
summary = json.load(open(summary_path, "r", encoding="utf-8"))
required_top = ["report_version", "packet_hash", "counts", "strictness", "key_linkage"]
for k in required_top:
    assert k in summary, k
assert summary["report_version"] == "proof_packet_verify_summary_v1"
packet_hash = "sha256:" + hashlib.sha256(open(packet_path, "rb").read()).hexdigest()
assert summary["packet_hash"] == packet_hash
counts = summary["counts"]
for k in ["matched", "mismatched", "missing", "extra", "fatal"]:
    assert k in counts, k
assert counts["mismatched"] == 0 and counts["missing"] == 0 and counts["extra"] == 0 and counts["fatal"] == 0
link = summary["key_linkage"]
for k in ["replay_report_hash", "record_bytes_sha256", "record_hash", "signing_key_id"]:
    assert k in link, k
assert isinstance(link["record_bytes_sha256"], str) and link["record_bytes_sha256"].startswith("sha256:")
assert isinstance(link["replay_report_hash"], str) and link["replay_report_hash"].startswith("sha256:")
print("PASS: verifier summary JSON includes required keys, counts, packet_hash, and key linkage fields")
print("SUMMARY_KEYS=" + ",".join(sorted(summary.keys())))
print("COUNTS=" + json.dumps(counts, sort_keys=True, separators=(',', ':')))
print("LINKAGE_KEYS=" + ",".join(sorted(link.keys())))
PY

case "$OUT1" in
  *"PASS: proof packet manifest + payload hashes verified"*) echo "PASS: verify stdout pass marker present run1" ;;
  *) echo "FAIL: missing pass marker in run1"; exit 1 ;;
esac
case "$OUT2" in
  *"PASS: proof packet manifest + payload hashes verified"*) echo "PASS: verify stdout pass marker present run2" ;;
  *) echo "FAIL: missing pass marker in run2"; exit 1 ;;
esac

echo
echo "Summary: proof-packet verifier summary JSON checks complete"
