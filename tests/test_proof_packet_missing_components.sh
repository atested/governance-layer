#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PP="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task132-proof-missing.XXXXXX")"
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

mk_valid_packet() {
  local out="$1"
  python3 - <<'PY' "$FIX" "$out"
import hashlib, io, json, sys, tarfile
from pathlib import Path
fix = Path(sys.argv[1]); out = Path(sys.argv[2])
files = {}
for rel in ["record.json","replay_audit_report.json","artifacts/request.txt","artifacts/response.txt"]:
    b = (fix/rel).read_bytes()
    files[rel] = b
manifest = {
    "proof_packet_version":"proof_packet_v1",
    "hash_algo":"sha256",
    "files":{rel:{"sha256":"sha256:"+hashlib.sha256(b).hexdigest(),"size_bytes":len(b)} for rel,b in sorted(files.items())},
    "source_summary":{
        "replay_report_hash":"sha256:"+hashlib.sha256(files["replay_audit_report.json"]).hexdigest(),
        "record_bytes_sha256":"sha256:"+hashlib.sha256(files["record.json"]).hexdigest(),
    }
}
try:
    rec = json.loads(files["record.json"].decode())
    if isinstance(rec.get("record_hash"), str):
        manifest["source_summary"]["record_hash"] = rec["record_hash"]
except Exception:
    pass
mb = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
def add(tf, name, data):
    ti = tarfile.TarInfo(name); ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=""; ti.gname=""; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(data))
out.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(out, "w:", format=tarfile.USTAR_FORMAT) as tf:
    add(tf, "manifest.json", mb)
    for rel,b in sorted(files.items()):
        add(tf, "payload/"+rel, b)
PY
}

run_verify_capture() {
  local bundle="$1" out_file="$2"
  set +e
  python3 "$PP" verify --bundle "$bundle" >"$out_file" 2>&1
  local rc=$?
  set -e
  echo "$rc"
}

rewrite_tar() {
  # rewrite_tar <src> <dst> <python-snippet receives names/data map + writes tar>
  local src="$1" dst="$2"
  python3 - <<'PY' "$src" "$dst"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
}

VALID="$TMPDIR_LOCAL/valid.tar"
mk_valid_packet "$VALID"

echo "--- T-PROOF-MISS-001: valid control passes (digest stable across two runs) ---"
RC1="$(run_verify_capture "$VALID" "$TMPDIR_LOCAL/valid1.out")"
RC2="$(run_verify_capture "$VALID" "$TMPDIR_LOCAL/valid2.out")"
[[ "$RC1" == "0" && "$RC2" == "0" ]] || { echo "FAIL: valid control rc run1=$RC1 run2=$RC2"; exit 1; }
assert_contains "valid control pass marker run1" "$(cat "$TMPDIR_LOCAL/valid1.out")" "PASS: proof packet manifest + payload hashes verified"
assert_contains "valid control pass marker run2" "$(cat "$TMPDIR_LOCAL/valid2.out")" "PASS: proof packet manifest + payload hashes verified"
VALID_SHA1="$(sha256_file "$TMPDIR_LOCAL/valid1.out")"
VALID_SHA2="$(sha256_file "$TMPDIR_LOCAL/valid2.out")"
echo "VALID_VERIFY_OUT_SHA256_RUN1=$VALID_SHA1"
echo "VALID_VERIFY_OUT_SHA256_RUN2=$VALID_SHA2"
[[ "$VALID_SHA1" == "$VALID_SHA2" ]] || { echo "FAIL: valid control verify output nondeterministic"; exit 1; }
echo "PASS: valid control verify output deterministic"

echo
echo "--- T-PROOF-MISS-002A: missing manifest.json fails (digest stable across two runs) ---"
MISS_MAN1="$TMPDIR_LOCAL/missing_manifest1.tar"
MISS_MAN2="$TMPDIR_LOCAL/missing_manifest2.tar"
python3 - <<'PY' "$VALID" "$MISS_MAN1"
import io, tarfile, sys
from pathlib import Path
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "manifest.json":
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
cp "$MISS_MAN1" "$MISS_MAN2"
RC1="$(run_verify_capture "$MISS_MAN1" "$TMPDIR_LOCAL/missman1.out")"
RC2="$(run_verify_capture "$MISS_MAN2" "$TMPDIR_LOCAL/missman2.out")"
[[ "$RC1" == "1" && "$RC2" == "1" ]] || { echo "FAIL: missing manifest rc run1=$RC1 run2=$RC2"; exit 1; }
assert_contains "missing manifest marker run1" "$(cat "$TMPDIR_LOCAL/missman1.out")" "FAIL: missing manifest.json"
assert_contains "missing manifest marker run2" "$(cat "$TMPDIR_LOCAL/missman2.out")" "FAIL: missing manifest.json"
MM_SHA1="$(sha256_file "$TMPDIR_LOCAL/missman1.out")"; MM_SHA2="$(sha256_file "$TMPDIR_LOCAL/missman2.out")"
echo "MISSING_MANIFEST_OUT_SHA256_RUN1=$MM_SHA1"
echo "MISSING_MANIFEST_OUT_SHA256_RUN2=$MM_SHA2"
[[ "$MM_SHA1" == "$MM_SHA2" ]] || { echo "FAIL: missing manifest output nondeterministic"; exit 1; }
echo "PASS: missing manifest failure output deterministic"

echo
echo "--- T-PROOF-MISS-002B: missing payload/record.json fails ---"
MISS_REC="$TMPDIR_LOCAL/missing_record.tar"
python3 - <<'PY' "$VALID" "$MISS_REC"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "payload/record.json":
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
RC="$(run_verify_capture "$MISS_REC" "$TMPDIR_LOCAL/missrec.out")"
[[ "$RC" == "1" ]] || { echo "FAIL: missing record rc=$RC"; exit 1; }
assert_contains "missing record marker" "$(cat "$TMPDIR_LOCAL/missrec.out")" "FAIL: manifest references missing payload member: record.json"

echo
echo "--- T-PROOF-MISS-002C: missing manifest-listed artifact fails ---"
MISS_ART="$TMPDIR_LOCAL/missing_artifact.tar"
python3 - <<'PY' "$VALID" "$MISS_ART"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "payload/artifacts/request.txt":
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
RC="$(run_verify_capture "$MISS_ART" "$TMPDIR_LOCAL/missart.out")"
[[ "$RC" == "1" ]] || { echo "FAIL: missing artifact rc=$RC"; exit 1; }
assert_contains "missing artifact marker" "$(cat "$TMPDIR_LOCAL/missart.out")" "FAIL: manifest references missing payload member: artifacts/request.txt"

echo
echo "--- T-PROOF-MISS-002D: missing payload/replay_audit_report.json fails ---"
MISS_RPT="$TMPDIR_LOCAL/missing_report.tar"
python3 - <<'PY' "$VALID" "$MISS_RPT"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "payload/replay_audit_report.json":
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
RC="$(run_verify_capture "$MISS_RPT" "$TMPDIR_LOCAL/missrpt.out")"
[[ "$RC" == "1" ]] || { echo "FAIL: missing replay report rc=$RC"; exit 1; }
assert_contains "missing replay report marker" "$(cat "$TMPDIR_LOCAL/missrpt.out")" "FAIL: manifest references missing payload member: replay_audit_report.json"

echo
echo "--- T-PROOF-MISS-002E: malformed manifest JSON fails ---"
BAD_JSON="$TMPDIR_LOCAL/badjson.tar"
python3 - <<'PY' "$VALID" "$BAD_JSON"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "manifest.json":
            bad=b'{"proof_packet_version":\n'
            ti=tarfile.TarInfo("manifest.json"); ti.size=len(bad); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=""; ti.gname=""; ti.mode=0o644
            dst.addfile(ti, io.BytesIO(bad)); continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
RC="$(run_verify_capture "$BAD_JSON" "$TMPDIR_LOCAL/badjson.out")"
[[ "$RC" == "1" ]] || { echo "FAIL: malformed manifest rc=$RC"; exit 1; }
assert_contains "malformed manifest marker" "$(cat "$TMPDIR_LOCAL/badjson.out")" "FAIL: malformed manifest json:"

echo
echo "--- T-PROOF-MISS-002F: manifest hash mismatch fails (digest stable across two runs) ---"
HASHBAD1="$TMPDIR_LOCAL/hashbad1.tar"
HASHBAD2="$TMPDIR_LOCAL/hashbad2.tar"
python3 - <<'PY' "$VALID" "$HASHBAD1"
import io, json, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src:
    members = src.getmembers()
    manifest = json.load(src.extractfile("manifest.json"))
    manifest["files"]["artifacts/request.txt"]["sha256"] = "sha256:" + ("0"*64)
    mb=(json.dumps(manifest, sort_keys=True, separators=(",", ":"))+"\n").encode()
    with tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
      for m in members:
        if m.name=="manifest.json":
          ti=tarfile.TarInfo("manifest.json"); ti.size=len(mb); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=""; ti.gname=""; ti.mode=0o644
          dst.addfile(ti, io.BytesIO(mb))
        else:
          data=src.extractfile(m).read() if m.isfile() else b""
          dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
PY
cp "$HASHBAD1" "$HASHBAD2"
RC1="$(run_verify_capture "$HASHBAD1" "$TMPDIR_LOCAL/hashbad1.out")"
RC2="$(run_verify_capture "$HASHBAD2" "$TMPDIR_LOCAL/hashbad2.out")"
[[ "$RC1" == "1" && "$RC2" == "1" ]] || { echo "FAIL: hash mismatch rc run1=$RC1 run2=$RC2"; exit 1; }
assert_contains "hash mismatch marker run1" "$(cat "$TMPDIR_LOCAL/hashbad1.out")" "FAIL: hash mismatch for artifacts/request.txt"
assert_contains "hash mismatch marker run2" "$(cat "$TMPDIR_LOCAL/hashbad2.out")" "FAIL: hash mismatch for artifacts/request.txt"
HB_SHA1="$(sha256_file "$TMPDIR_LOCAL/hashbad1.out")"; HB_SHA2="$(sha256_file "$TMPDIR_LOCAL/hashbad2.out")"
echo "HASH_MISMATCH_OUT_SHA256_RUN1=$HB_SHA1"
echo "HASH_MISMATCH_OUT_SHA256_RUN2=$HB_SHA2"
[[ "$HB_SHA1" == "$HB_SHA2" ]] || { echo "FAIL: hash mismatch output nondeterministic"; exit 1; }
echo "PASS: hash mismatch failure output deterministic"

echo
echo "--- T-PROOF-MISS-002G: extra payload member not in manifest fails ---"
EXTRA="$TMPDIR_LOCAL/extra.tar"
python3 - <<'PY' "$VALID" "$EXTRA"
import io, tarfile, sys
srcp, dstp = sys.argv[1:3]
with tarfile.open(srcp, "r:") as src, tarfile.open(dstp, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
    ti=tarfile.TarInfo("payload/artifacts/extra.txt"); data=b"extra\n"
    ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=""; ti.gname=""; ti.mode=0o644
    dst.addfile(ti, io.BytesIO(data))
PY
RC="$(run_verify_capture "$EXTRA" "$TMPDIR_LOCAL/extra.out")"
[[ "$RC" == "1" ]] || { echo "FAIL: extra payload rc=$RC"; exit 1; }
assert_contains "extra payload marker" "$(cat "$TMPDIR_LOCAL/extra.out")" "FAIL: unexpected payload member not in manifest: artifacts/extra.txt"

echo
echo "Summary: proof-packet missing-components negative controls complete"
