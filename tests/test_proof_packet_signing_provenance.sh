#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task127-proof-signprov.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

assert_contains() {
  local name="$1" hay="$2" needle="$3"
  [[ "$hay" == *"$needle"* ]] || { echo "FAIL: $name (missing '$needle')"; exit 1; }
  echo "PASS: $name"
}

make_inputs_with_signing_id() {
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
doc["signing_key_id"] = "ed25519:test-key-1234"
doc["record_hash"] = "sha256:" + verify_mod.sha256_hex(verify_mod.signing_preimage_payload(doc))
doc["signature"] = None
dst.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
  cp "$FIX/replay_audit_report.json" "$dir/replay_audit_report.json"
  cp -R "$FIX/artifacts" "$dir/artifacts"
}

pack_verify() {
  local tag="$1" in_dir="$2"
  local packet="$TMPDIR_LOCAL/${tag}.tar"
  local summary="$TMPDIR_LOCAL/${tag}.summary.json"
  python3 "$PACKER" pack \
    --record "$in_dir/record.json" \
    --artifacts-dir "$in_dir/artifacts" \
    --replay-audit-report "$in_dir/replay_audit_report.json" \
    --out "$packet" > "$TMPDIR_LOCAL/${tag}.pack.log"
  python3 "$PACKER" verify --bundle "$packet" --summary-json "$summary" > "$TMPDIR_LOCAL/${tag}.verify.log"
  echo "$packet|$summary"
}

echo "--- T-PROOF-SIGNPROV-001: source_summary provenance fields + determinism ---"
BASE="$TMPDIR_LOCAL/base"
make_inputs_with_signing_id "$BASE"
IFS='|' read -r P1 S1 < <(pack_verify run1 "$BASE")
IFS='|' read -r P2 S2 < <(pack_verify run2 "$BASE")
PP1_SHA="$(sha256_file "$P1")"
PP2_SHA="$(sha256_file "$P2")"
VS1_SHA="$(sha256_file "$S1")"
VS2_SHA="$(sha256_file "$S2")"
echo "PROOF_PACKET_SHA256_RUN1=$PP1_SHA"
echo "PROOF_PACKET_SHA256_RUN2=$PP2_SHA"
echo "VERIFY_SUMMARY_SHA256_RUN1=$VS1_SHA"
echo "VERIFY_SUMMARY_SHA256_RUN2=$VS2_SHA"
[[ "$PP1_SHA" == "$PP2_SHA" ]] || { echo "FAIL: packet digest nondeterministic"; exit 1; }
[[ "$VS1_SHA" == "$VS2_SHA" ]] || { echo "FAIL: verifier summary digest nondeterministic"; exit 1; }
echo "PASS: proof-packet + verifier summary digests deterministic across two runs"

python3 - <<'PY' "$P1" "$BASE/record.json"
import hashlib, json, sys, tarfile
pp, rec = sys.argv[1:3]
record_bytes = open(rec, "rb").read()
record_sha = "sha256:" + hashlib.sha256(record_bytes).hexdigest()
record_doc = json.loads(record_bytes.decode("utf-8"))
with tarfile.open(pp, "r:") as tf:
    manifest = json.load(tf.extractfile("manifest.json"))
    src = manifest["source_summary"]
    files = manifest["files"]
    assert src["record_bytes_sha256"] == files["record.json"]["sha256"] == record_sha
    assert src["record_hash"] == record_doc["record_hash"]
    assert src["signing_key_id"] == "ed25519:test-key-1234"
print("PASS: source_summary includes record_hash, signing_key_id, and record_bytes_sha256 linkage")
PY

echo
echo "--- T-PROOF-SIGNPROV-002: record_bytes_sha256 linkage mismatch fails verify ---"
BAD="$TMPDIR_LOCAL/record_link_bad.tar"
cp "$P1" "$BAD"
python3 - <<'PY' "$BAD"
import io, json, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src:
    members = src.getmembers()
    manifest = json.load(src.extractfile("manifest.json"))
    manifest["source_summary"]["record_bytes_sha256"] = "sha256:" + ("f" * 64)
    mb = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
        for m in members:
            if m.name == "manifest.json":
                ti = tarfile.TarInfo("manifest.json")
                ti.size = len(mb); ti.mtime = 0; ti.uid = 0; ti.gid = 0; ti.uname = ""; ti.gname = ""; ti.mode = 0o644
                dst.addfile(ti, io.BytesIO(mb))
            else:
                data = src.extractfile(m).read() if m.isfile() else b""
                dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
tmp.replace(p)
PY
set +e
OUT_BAD="$(python3 "$PACKER" verify --bundle "$BAD" 2>&1)"
RC_BAD=$?
set -e
[[ "$RC_BAD" == "1" ]] || { echo "FAIL: linkage mismatch verify rc=$RC_BAD"; exit 1; }
assert_contains "record_bytes_sha256 linkage mismatch marker" "$OUT_BAD" "FAIL: source_summary record_bytes_sha256 mismatch vs manifest file hash"

echo
echo "Summary: proof-packet signing provenance summary checks complete"
