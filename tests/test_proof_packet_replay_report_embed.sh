#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKER="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task130-proof-embed.XXXXXX")"
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

make_inputs() {
  local dir="$1"
  mkdir -p "$dir"
  cp "$FIX/record.json" "$dir/record.json"
  cp "$FIX/replay_audit_report.json" "$dir/replay_audit_report.json"
  cp -R "$FIX/artifacts" "$dir/artifacts"
}

pack_and_verify() {
  local tag="$1" in_dir="$2"
  local pkt="$TMPDIR_LOCAL/${tag}.tar"
  local sum="$TMPDIR_LOCAL/${tag}.summary.json"
  python3 "$PACKER" pack \
    --record "$in_dir/record.json" \
    --artifacts-dir "$in_dir/artifacts" \
    --replay-audit-report "$in_dir/replay_audit_report.json" \
    --out "$pkt" > "$TMPDIR_LOCAL/${tag}.pack.log"
  python3 "$PACKER" verify --bundle "$pkt" --summary-json "$sum" > "$TMPDIR_LOCAL/${tag}.verify.log"
  echo "$pkt|$sum"
}

echo "--- T-PROOF-EMBED-001: replay audit report embedded and linked deterministically ---"
BASE="$TMPDIR_LOCAL/base"
make_inputs "$BASE"
IFS='|' read -r P1 S1 < <(pack_and_verify run1 "$BASE")
IFS='|' read -r P2 S2 < <(pack_and_verify run2 "$BASE")
PP1_SHA="$(sha256_file "$P1")"
PP2_SHA="$(sha256_file "$P2")"
VS1_SHA="$(sha256_file "$S1")"
VS2_SHA="$(sha256_file "$S2")"
echo "PROOF_PACKET_SHA256_RUN1=$PP1_SHA"
echo "PROOF_PACKET_SHA256_RUN2=$PP2_SHA"
echo "VERIFY_SUMMARY_SHA256_RUN1=$VS1_SHA"
echo "VERIFY_SUMMARY_SHA256_RUN2=$VS2_SHA"
[[ "$PP1_SHA" == "$PP2_SHA" ]] || { echo "FAIL: proof-packet digest nondeterministic"; exit 1; }
[[ "$VS1_SHA" == "$VS2_SHA" ]] || { echo "FAIL: verifier summary digest nondeterministic"; exit 1; }
echo "PASS: pack+verify digests deterministic across two runs"

python3 - <<'PY' "$P1" "$BASE/replay_audit_report.json"
import hashlib, json, sys, tarfile
pp, rpt = sys.argv[1:3]
with tarfile.open(pp, "r:") as tf:
    names = tf.getnames()
    assert "payload/replay_audit_report.json" in names, names
    manifest = json.load(tf.extractfile("manifest.json"))
    files = manifest["files"]
    src = manifest["source_summary"]
    expect = "sha256:" + hashlib.sha256(open(rpt, "rb").read()).hexdigest()
    assert files["replay_audit_report.json"]["sha256"] == expect
    assert src["replay_report_hash"] == expect
print("PASS: replay audit report path contract and source_summary linkage valid")
PY

echo
echo "--- T-PROOF-EMBED-002: missing replay audit report input fails pack ---"
MISS="$TMPDIR_LOCAL/missing"
cp -R "$BASE" "$MISS"
rm -f "$MISS/replay_audit_report.json"
set +e
OUT_MISS="$(python3 "$PACKER" pack --record "$MISS/record.json" --artifacts-dir "$MISS/artifacts" --replay-audit-report "$MISS/replay_audit_report.json" --out "$TMPDIR_LOCAL/missing.tar" 2>&1)"
RC_MISS=$?
set -e
[[ "$RC_MISS" != "0" ]] || { echo "FAIL: missing replay report pack unexpectedly succeeded"; exit 1; }
assert_contains "missing replay audit report pack marker" "$OUT_MISS" "ERROR: file not found"

echo
echo "--- T-PROOF-EMBED-003: tampered replay audit report payload fails verify ---"
TAMPER="$TMPDIR_LOCAL/tamper.tar"
cp "$P1" "$TAMPER"
python3 - <<'PY' "$TAMPER"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "payload/replay_audit_report.json":
            data = b'{"tampered":true}\n'
            m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
tmp.replace(p)
PY
set +e
OUT_TAMP="$(python3 "$PACKER" verify --bundle "$TAMPER" 2>&1)"
RC_TAMP=$?
set -e
[[ "$RC_TAMP" == "1" ]] || { echo "FAIL: tampered replay report verify rc=$RC_TAMP"; exit 1; }
assert_contains "tampered replay audit report marker" "$OUT_TAMP" "FAIL: hash mismatch for replay_audit_report.json"

echo
echo "--- T-PROOF-EMBED-004: source_summary linkage mismatch fails verify ---"
LINKBAD="$TMPDIR_LOCAL/linkbad.tar"
cp "$P1" "$LINKBAD"
python3 - <<'PY' "$LINKBAD"
import io, json, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src:
    members = src.getmembers()
    manifest = json.load(src.extractfile("manifest.json"))
    manifest["source_summary"]["replay_report_hash"] = "sha256:" + ("0" * 64)
    manifest_b = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
        for m in members:
            if m.name == "manifest.json":
                ti = tarfile.TarInfo("manifest.json")
                ti.size = len(manifest_b); ti.mtime = 0; ti.uid = 0; ti.gid = 0; ti.uname = ""; ti.gname = ""; ti.mode = 0o644
                dst.addfile(ti, io.BytesIO(manifest_b))
            else:
                data = src.extractfile(m).read() if m.isfile() else b""
                dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
tmp.replace(p)
PY
set +e
OUT_LINK="$(python3 "$PACKER" verify --bundle "$LINKBAD" 2>&1)"
RC_LINK=$?
set -e
[[ "$RC_LINK" == "1" ]] || { echo "FAIL: source_summary linkage mismatch verify rc=$RC_LINK"; exit 1; }
assert_contains "source_summary linkage mismatch marker" "$OUT_LINK" "FAIL: source_summary replay_report_hash mismatch vs manifest file hash"

echo
echo "Summary: proof-packet replay audit report embedding checks complete"
