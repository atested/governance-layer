#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PP="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task125-proof-verify.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

mk_valid_bundle() {
  local out="$1"
  python3 - <<'PY' "$FIX" "$out"
import hashlib, io, json, sys, tarfile
from pathlib import Path

fix = Path(sys.argv[1])
out = Path(sys.argv[2])
files = {}
for rel in ["record.json","replay_audit_report.json","artifacts/request.txt","artifacts/response.txt"]:
    p = fix/rel
    b = p.read_bytes()
    files[rel] = b

manifest = {
    "proof_packet_version": "proof_packet_v1",
    "hash_algo": "sha256",
    "files": {rel: {"sha256": "sha256:"+hashlib.sha256(b).hexdigest(), "size_bytes": len(b)} for rel,b in sorted(files.items())},
    "source_summary": {
        "record_hash": json.loads(files["record.json"].decode())["record_hash"],
        "record_bytes_sha256": "sha256:" + hashlib.sha256(files["record.json"]).hexdigest(),
        "replay_report_hash": "sha256:"+hashlib.sha256(files["replay_audit_report.json"]).hexdigest(),
    },
}
manifest_b = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()

def add(tf, name, data):
    ti = tarfile.TarInfo(name)
    ti.size = len(data); ti.mtime = 0; ti.uid = 0; ti.gid = 0; ti.uname = ""; ti.gname = ""; ti.mode = 0o644
    tf.addfile(ti, io.BytesIO(data))

out.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(out, "w:", format=tarfile.USTAR_FORMAT) as tf:
    add(tf, "manifest.json", manifest_b)
    for rel, b in sorted(files.items()):
        add(tf, "payload/"+rel, b)
PY
}

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

BUNDLE="$TMPDIR_LOCAL/valid.tar"
mk_valid_bundle "$BUNDLE"

echo "--- T-PROOF-VERIFY-001: valid packet passes + deterministic summary digest ---"
SUM1="$TMPDIR_LOCAL/summary1.json"
SUM2="$TMPDIR_LOCAL/summary2.json"
OUT1="$(python3 "$PP" verify --bundle "$BUNDLE" --summary-json "$SUM1")"
OUT2="$(python3 "$PP" verify --bundle "$BUNDLE" --summary-json "$SUM2")"
assert_contains "valid verify pass marker run1" "$OUT1" "PASS: proof packet manifest + payload hashes verified"
assert_contains "valid verify pass marker run2" "$OUT2" "PASS: proof packet manifest + payload hashes verified"
SHA1="$(sha256_file "$SUM1")"
SHA2="$(sha256_file "$SUM2")"
[[ "$SHA1" == "$SHA2" ]] || { echo "FAIL: summary digest mismatch ($SHA1 != $SHA2)"; exit 1; }
echo "VERIFY_SUMMARY_SHA256_RUN1=$SHA1"
echo "VERIFY_SUMMARY_SHA256_RUN2=$SHA2"
echo "PASS: verifier summary digest deterministic across two runs"

echo
echo "--- T-PROOF-VERIFY-002: hash mismatch fails ---"
TAMPER="$TMPDIR_LOCAL/tamper_hash.tar"
cp "$BUNDLE" "$TAMPER"
python3 - <<'PY' "$TAMPER"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "payload/artifacts/request.txt":
            data = b"TAMPERED\n"
            m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
tmp.replace(p)
PY
set +e
OUT_FAIL="$(python3 "$PP" verify --bundle "$TAMPER" 2>&1)"
RC_FAIL=$?
set -e
[[ "$RC_FAIL" == "1" ]] || { echo "FAIL: hash mismatch exit rc=$RC_FAIL"; exit 1; }
assert_contains "hash mismatch marker" "$OUT_FAIL" "FAIL: hash mismatch for artifacts/request.txt"

echo
echo "--- T-PROOF-VERIFY-003: extra payload member fails ---"
EXTRA="$TMPDIR_LOCAL/extra.tar"
cp "$BUNDLE" "$EXTRA"
python3 - <<'PY' "$EXTRA"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
    m = tarfile.TarInfo("payload/artifacts/extra.txt")
    data = b"extra\n"
    m.size = len(data); m.mtime = 0; m.uid = 0; m.gid = 0; m.uname = ""; m.gname = ""; m.mode = 0o644
    dst.addfile(m, io.BytesIO(data))
tmp.replace(p)
PY
set +e
OUT_EXTRA="$(python3 "$PP" verify --bundle "$EXTRA" 2>&1)"
RC_EXTRA=$?
set -e
[[ "$RC_EXTRA" == "1" ]] || { echo "FAIL: extra payload exit rc=$RC_EXTRA"; exit 1; }
assert_contains "extra payload marker" "$OUT_EXTRA" "FAIL: unexpected payload member not in manifest: artifacts/extra.txt"

echo
echo "--- T-PROOF-VERIFY-004: duplicate manifest path fails ---"
DUP="$TMPDIR_LOCAL/dup.tar"
cp "$BUNDLE" "$DUP"
python3 - <<'PY' "$DUP"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); tmp = p.with_suffix(".tmp")
dup_manifest = ('{\"proof_packet_version\":\"proof_packet_v1\",\"hash_algo\":\"sha256\",\"files\":{\"record.json\":{\"sha256\":\"sha256:' + ('0'*64) + '\",\"size_bytes\":1},\"record.json\":{\"sha256\":\"sha256:' + ('1'*64) + '\",\"size_bytes\":2}},\"source_summary\":{}}\\n').encode()
with tarfile.open(p, "r:") as src, tarfile.open(tmp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "manifest.json":
            m2 = tarfile.TarInfo("manifest.json")
            m2.size = len(dup_manifest); m2.mtime = 0; m2.uid = 0; m2.gid = 0; m2.uname = ""; m2.gname = ""; m2.mode = 0o644
            dst.addfile(m2, io.BytesIO(dup_manifest))
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
tmp.replace(p)
PY
set +e
OUT_DUP="$(python3 "$PP" verify --bundle "$DUP" 2>&1)"
RC_DUP=$?
set -e
[[ "$RC_DUP" == "1" ]] || { echo "FAIL: duplicate manifest exit rc=$RC_DUP"; exit 1; }
assert_contains "duplicate path marker" "$OUT_DUP" "FAIL: duplicate manifest path: record.json"

echo
echo "Summary: proof-packet manifest verifier tests complete"
