#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PP="$ROOT/scripts/proof-packet.py"
FIX="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task126-proof-tamper.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

mk_valid_bundle() {
  local out="$1"
  python3 - <<'PY' "$FIX" "$out"
import hashlib, io, json, sys, tarfile
from pathlib import Path
fix = Path(sys.argv[1]); out = Path(sys.argv[2])
files = {}
for rel in ["record.json","replay_audit_report.json","artifacts/request.txt","artifacts/response.txt"]:
    b = (fix/rel).read_bytes(); files[rel] = b
manifest = {
  "proof_packet_version":"proof_packet_v1",
  "hash_algo":"sha256",
  "files": {rel: {"sha256":"sha256:"+hashlib.sha256(b).hexdigest(),"size_bytes":len(b)} for rel,b in sorted(files.items())},
  "source_summary": {
    "record_hash": json.loads(files["record.json"].decode())["record_hash"],
    "record_bytes_sha256": "sha256:"+hashlib.sha256(files["record.json"]).hexdigest(),
    "replay_report_hash":"sha256:"+hashlib.sha256(files["replay_audit_report.json"]).hexdigest(),
  },
}
mb = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
def add(tf, name, data):
    ti = tarfile.TarInfo(name); ti.size=len(data); ti.mtime=0; ti.uid=0; ti.gid=0; ti.uname=""; ti.gname=""; ti.mode=0o644
    tf.addfile(ti, io.BytesIO(data))
with tarfile.open(out, "w:", format=tarfile.USTAR_FORMAT) as tf:
    add(tf, "manifest.json", mb)
    for rel,b in sorted(files.items()):
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

run_verify_case() {
  local bundle="$1"
  set +e
  local out
  out="$(python3 "$PP" verify --bundle "$bundle" 2>&1)"
  local rc=$?
  set -e
  printf '%s\n' "$rc"
  printf '%s\n' "$out" > "$TMPDIR_LOCAL/case.out"
}

VALID="$TMPDIR_LOCAL/valid.tar"
mk_valid_bundle "$VALID"

echo "--- T-PROOF-TAMPER-001: valid packet passes (control) ---"
OUT_VALID1="$TMPDIR_LOCAL/valid1.out"
OUT_VALID2="$TMPDIR_LOCAL/valid2.out"
python3 "$PP" verify --bundle "$VALID" > "$OUT_VALID1"
python3 "$PP" verify --bundle "$VALID" > "$OUT_VALID2"
V1_SHA="$(sha256_file "$OUT_VALID1")"
V2_SHA="$(sha256_file "$OUT_VALID2")"
[[ "$V1_SHA" == "$V2_SHA" ]] || { echo "FAIL: valid verifier output digest mismatch"; exit 1; }
assert_contains "valid control pass marker" "$(cat "$OUT_VALID1")" "PASS: proof packet manifest + payload hashes verified"
echo "VALID_VERIFY_SHA256_RUN1=$V1_SHA"
echo "VALID_VERIFY_SHA256_RUN2=$V2_SHA"
echo "PASS: valid verifier output deterministic across two runs"

echo
echo "--- T-PROOF-TAMPER-002: payload byte tamper fails ---"
PAYLOAD_TAMPER="$TMPDIR_LOCAL/payload_tamper.tar"
cp "$VALID" "$PAYLOAD_TAMPER"
python3 - <<'PY' "$PAYLOAD_TAMPER"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "payload/artifacts/request.txt":
            data = b"TAMPERED\n"; m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
rc="$(run_verify_case "$PAYLOAD_TAMPER")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: payload tamper rc=$rc"; exit 1; }
assert_contains "payload tamper marker" "$out" "FAIL: hash mismatch for artifacts/request.txt"

echo
echo "--- T-PROOF-TAMPER-003: manifest hash tamper fails ---"
MANIFEST_HASH_TAMPER="$TMPDIR_LOCAL/manifest_hash_tamper.tar"
cp "$VALID" "$MANIFEST_HASH_TAMPER"
python3 - <<'PY' "$MANIFEST_HASH_TAMPER"
import io, json, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "manifest.json":
            doc = json.loads(data.decode())
            doc["files"]["artifacts/request.txt"]["sha256"] = "sha256:" + ("0" * 64)
            data = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()
            m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
rc="$(run_verify_case "$MANIFEST_HASH_TAMPER")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: manifest hash tamper rc=$rc"; exit 1; }
assert_contains "manifest hash tamper marker" "$out" "FAIL: hash mismatch for artifacts/request.txt"

echo
echo "--- T-PROOF-TAMPER-004: missing payload member fails ---"
MISSING_PAYLOAD="$TMPDIR_LOCAL/missing_payload.tar"
cp "$VALID" "$MISSING_PAYLOAD"
python3 - <<'PY' "$MISSING_PAYLOAD"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "payload/artifacts/request.txt":
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
rc="$(run_verify_case "$MISSING_PAYLOAD")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: missing payload rc=$rc"; exit 1; }
assert_contains "missing payload marker" "$out" "FAIL: manifest references missing payload member: artifacts/request.txt"

echo
echo "--- T-PROOF-TAMPER-005: extra payload member fails ---"
EXTRA_PAYLOAD="$TMPDIR_LOCAL/extra_payload.tar"
cp "$VALID" "$EXTRA_PAYLOAD"
python3 - <<'PY' "$EXTRA_PAYLOAD"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
    m = tarfile.TarInfo("payload/artifacts/extra.txt")
    data = b"extra\n"
    m.size=len(data); m.mtime=0; m.uid=0; m.gid=0; m.uname=""; m.gname=""; m.mode=0o644
    dst.addfile(m, io.BytesIO(data))
t.replace(p)
PY
rc="$(run_verify_case "$EXTRA_PAYLOAD")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: extra payload rc=$rc"; exit 1; }
assert_contains "extra payload marker" "$out" "FAIL: unexpected payload member not in manifest: artifacts/extra.txt"

echo
echo "--- T-PROOF-TAMPER-006A: malformed manifest JSON fails ---"
BAD_JSON="$TMPDIR_LOCAL/malformed_manifest.tar"
cp "$VALID" "$BAD_JSON"
python3 - <<'PY' "$BAD_JSON"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "manifest.json":
            data = b"{\"proof_packet_version\":\n"
            m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
rc="$(run_verify_case "$BAD_JSON")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: malformed manifest rc=$rc"; exit 1; }
assert_contains "malformed manifest marker" "$out" "FAIL: malformed manifest json:"

echo
echo "--- T-PROOF-TAMPER-006B: missing required field fails ---"
MISSING_FIELD="$TMPDIR_LOCAL/missing_field.tar"
cp "$VALID" "$MISSING_FIELD"
python3 - <<'PY' "$MISSING_FIELD"
import io, json, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        data = src.extractfile(m).read() if m.isfile() else b""
        if m.name == "manifest.json":
            doc = json.loads(data.decode())
            del doc["hash_algo"]
            data = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()
            m.size = len(data)
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
rc="$(run_verify_case "$MISSING_FIELD")"; out="$(cat "$TMPDIR_LOCAL/case.out")"
[[ "$rc" == "1" ]] || { echo "FAIL: missing field rc=$rc"; exit 1; }
assert_contains "missing field marker" "$out" "FAIL: manifest missing required key: hash_algo"

echo
echo "--- T-PROOF-TAMPER-007: duplicate manifest path fails ---"
DUP="$TMPDIR_LOCAL/dup_manifest.tar"
cp "$VALID" "$DUP"
python3 - <<'PY' "$DUP"
import io, tarfile, sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.with_suffix(".tmp")
dup = ('{\"proof_packet_version\":\"proof_packet_v1\",\"hash_algo\":\"sha256\",\"files\":{\"record.json\":{\"sha256\":\"sha256:' + ('0'*64) + '\",\"size_bytes\":1},\"record.json\":{\"sha256\":\"sha256:' + ('1'*64) + '\",\"size_bytes\":2}},\"source_summary\":{}}\\n').encode()
with tarfile.open(p, "r:") as src, tarfile.open(t, "w:", format=tarfile.USTAR_FORMAT) as dst:
    for m in src.getmembers():
        if m.name == "manifest.json":
            m2 = tarfile.TarInfo("manifest.json")
            m2.size=len(dup); m2.mtime=0; m2.uid=0; m2.gid=0; m2.uname=""; m2.gname=""; m2.mode=0o644
            dst.addfile(m2, io.BytesIO(dup))
            continue
        data = src.extractfile(m).read() if m.isfile() else b""
        dst.addfile(m, io.BytesIO(data) if m.isfile() else None)
t.replace(p)
PY
set +e
OUT_DUP1="$(python3 "$PP" verify --bundle "$DUP" 2>&1)"; RC_DUP1=$?
OUT_DUP2="$(python3 "$PP" verify --bundle "$DUP" 2>&1)"; RC_DUP2=$?
set -e
[[ "$RC_DUP1" == "1" && "$RC_DUP2" == "1" ]] || { echo "FAIL: duplicate manifest rc=$RC_DUP1/$RC_DUP2"; exit 1; }
assert_contains "duplicate manifest marker run1" "$OUT_DUP1" "FAIL: duplicate manifest path: record.json"
assert_contains "duplicate manifest marker run2" "$OUT_DUP2" "FAIL: duplicate manifest path: record.json"
printf '%s\n' "$OUT_DUP1" > "$TMPDIR_LOCAL/dup1.out"
printf '%s\n' "$OUT_DUP2" > "$TMPDIR_LOCAL/dup2.out"
D1="$(sha256_file "$TMPDIR_LOCAL/dup1.out")"
D2="$(sha256_file "$TMPDIR_LOCAL/dup2.out")"
[[ "$D1" == "$D2" ]] || { echo "FAIL: duplicate manifest output nondeterministic"; exit 1; }
echo "DUP_FAIL_SHA256_RUN1=$D1"
echo "DUP_FAIL_SHA256_RUN2=$D2"
echo "PASS: duplicate-manifest failure output deterministic across two runs"

echo
echo "Summary: proof-packet tamper matrix complete"
