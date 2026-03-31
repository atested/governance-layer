#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/task113-tamper.XXXXXX")"
trap 'rm -rf "$TMPDIR"' EXIT

PACK="$ROOT/scripts/attest/bundle.py"
VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
SAMPLE="$ROOT/tests/fixtures/attestation_bundle/sample"

fail() { echo "FAIL: $*"; exit 1; }
pass() { echo "PASS: $*"; }

run_expect() {
  local label="$1" expected_rc="$2" expect_substr="$3"
  shift 3
  local out rc
  set +e
  out="$("$@" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$out"
  [[ "$rc" -eq "$expected_rc" ]] || fail "$label exit=$rc expected=$expected_rc"
  if [[ -n "$expect_substr" ]]; then
    [[ "$out" == *"$expect_substr"* ]] || fail "$label missing substring: $expect_substr"
  fi
  pass "$label (exit=$rc)"
}

pack_bundle() {
  local out_path="$1"
  python3 "$PACK" pack --input-dir "$SAMPLE" --out "$out_path" >/dev/null
}

tamper_tar_payload_bytes() {
  local src="$1" dst="$2" rel="$3" new_bytes="$4"
  python3 - "$src" "$dst" "$rel" "$new_bytes" <<'PY'
import io, sys, tarfile
src, dst, rel, data = sys.argv[1:5]
target = f"payload/{rel}"
with tarfile.open(src, "r:") as tin, tarfile.open(dst, "w:", format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        f = tin.extractfile(m) if m.isfile() else None
        blob = f.read() if f else b""
        if m.isfile() and m.name == target:
            blob = data.encode("utf-8")
        nm = tarfile.TarInfo(m.name)
        nm.type = tarfile.REGTYPE if m.isfile() else m.type
        nm.mode = m.mode
        nm.uid = m.uid
        nm.gid = m.gid
        nm.uname = m.uname
        nm.gname = m.gname
        nm.mtime = m.mtime
        if m.isfile():
            nm.size = len(blob)
            tout.addfile(nm, io.BytesIO(blob))
        else:
            tout.addfile(nm)
PY
}

remove_tar_member() {
  local src="$1" dst="$2" target="$3"
  python3 - "$src" "$dst" "$target" <<'PY'
import io, sys, tarfile
src, dst, target = sys.argv[1:4]
with tarfile.open(src, "r:") as tin, tarfile.open(dst, "w:", format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        if m.name == target:
            continue
        f = tin.extractfile(m) if m.isfile() else None
        blob = f.read() if f else b""
        nm = tarfile.TarInfo(m.name)
        nm.type = tarfile.REGTYPE if m.isfile() else m.type
        nm.mode = m.mode
        nm.uid = m.uid
        nm.gid = m.gid
        nm.uname = m.uname
        nm.gname = m.gname
        nm.mtime = m.mtime
        if m.isfile():
            nm.size = len(blob)
            tout.addfile(nm, io.BytesIO(blob))
        else:
            tout.addfile(nm)
PY
}

add_tar_member() {
  local src="$1" dst="$2" target="$3" text="$4"
  python3 - "$src" "$dst" "$target" "$text" <<'PY'
import io, sys, tarfile
src, dst, target, text = sys.argv[1:5]
with tarfile.open(src, "r:") as tin, tarfile.open(dst, "w:", format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        f = tin.extractfile(m) if m.isfile() else None
        blob = f.read() if f else b""
        nm = tarfile.TarInfo(m.name)
        nm.type = tarfile.REGTYPE if m.isfile() else m.type
        nm.mode = m.mode
        nm.uid = m.uid
        nm.gid = m.gid
        nm.uname = m.uname
        nm.gname = m.gname
        nm.mtime = m.mtime
        if m.isfile():
            nm.size = len(blob)
            tout.addfile(nm, io.BytesIO(blob))
        else:
            tout.addfile(nm)
    blob = text.encode("utf-8")
    nm = tarfile.TarInfo(target)
    nm.type = tarfile.REGTYPE
    nm.mode = 0o644
    nm.uid = 0
    nm.gid = 0
    nm.uname = ""
    nm.gname = ""
    nm.mtime = 0
    nm.size = len(blob)
    tout.addfile(nm, io.BytesIO(blob))
PY
}

rewrite_manifest() {
  local src="$1" dst="$2" mode="$3"
  python3 - "$src" "$dst" "$mode" <<'PY'
import io, json, sys, tarfile
src, dst, mode = sys.argv[1:4]

def mutate(raw: bytes, mode: str) -> bytes:
    if mode == "hash_tamper":
        doc = json.loads(raw.decode("utf-8"))
        for ent in doc["files"]:
            if ent["path"] == "artifacts/request.txt":
                ent["sha256"] = "sha256:" + ("0" * 64)
                break
        return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if mode == "malformed_json":
        return b'{"bundle_version":"attestation_bundle_v1","hash_algo":"sha256","files":[\n'
    if mode == "missing_hash_algo":
        doc = json.loads(raw.decode("utf-8"))
        doc.pop("hash_algo", None)
        return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if mode == "duplicate_entry":
        doc = json.loads(raw.decode("utf-8"))
        dup = None
        for ent in doc["files"]:
            if ent["path"] == "artifacts/request.txt":
                dup = dict(ent)
                break
        if dup is None:
            raise SystemExit("request.txt manifest entry not found")
        doc["files"].append(dup)
        return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    raise SystemExit(f"unknown mode: {mode}")

with tarfile.open(src, "r:") as tin, tarfile.open(dst, "w:", format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        f = tin.extractfile(m) if m.isfile() else None
        blob = f.read() if f else b""
        if m.isfile() and m.name == "manifest.json":
            blob = mutate(blob, mode)
        nm = tarfile.TarInfo(m.name)
        nm.type = tarfile.REGTYPE if m.isfile() else m.type
        nm.mode = m.mode
        nm.uid = m.uid
        nm.gid = m.gid
        nm.uname = m.uname
        nm.gname = m.gname
        nm.mtime = m.mtime
        if m.isfile():
            nm.size = len(blob)
            tout.addfile(nm, io.BytesIO(blob))
        else:
            tout.addfile(nm)
PY
}

VALID="$TMPDIR/valid.tar"
pack_bundle "$VALID"

echo "--- T-BUNDLE-TAMPER-001: valid bundle passes (control) ---"
run_expect "valid bundle" 0 "PASS: attestation bundle manifest + payload hashes verified" \
  python3 "$VERIFY" "$VALID"

echo
echo "--- T-BUNDLE-TAMPER-002: payload tamper fails ---"
PAYLOAD_TAMPER="$TMPDIR/payload_tamper.tar"
tamper_tar_payload_bytes "$VALID" "$PAYLOAD_TAMPER" "artifacts/request.txt" "tampered-request-bytes"
run_expect "payload tamper" 1 "hash mismatch for artifacts/request.txt" \
  python3 "$VERIFY" "$PAYLOAD_TAMPER"

echo
echo "--- T-BUNDLE-TAMPER-003: manifest hash tamper fails ---"
MANIFEST_HASH_TAMPER="$TMPDIR/manifest_hash_tamper.tar"
rewrite_manifest "$VALID" "$MANIFEST_HASH_TAMPER" "hash_tamper"
run_expect "manifest hash tamper" 1 "hash mismatch for artifacts/request.txt" \
  python3 "$VERIFY" "$MANIFEST_HASH_TAMPER"

echo
echo "--- T-BUNDLE-TAMPER-004: missing manifest-listed payload member fails ---"
MISSING_FILE="$TMPDIR/missing_payload.tar"
remove_tar_member "$VALID" "$MISSING_FILE" "payload/artifacts/request.txt"
run_expect "missing file" 1 "manifest references missing bundle member: artifacts/request.txt" \
  python3 "$VERIFY" "$MISSING_FILE"

echo
echo "--- T-BUNDLE-TAMPER-005: extra unexpected payload member fails ---"
EXTRA_FILE="$TMPDIR/extra_payload.tar"
add_tar_member "$VALID" "$EXTRA_FILE" "payload/artifacts/extra.txt" "extra"
run_expect "extra file" 1 "unexpected payload member not in manifest: artifacts/extra.txt" \
  python3 "$VERIFY" "$EXTRA_FILE"

echo
echo "--- T-BUNDLE-TAMPER-006A: malformed manifest JSON fails ---"
MALFORMED_JSON="$TMPDIR/malformed_json.tar"
rewrite_manifest "$VALID" "$MALFORMED_JSON" "malformed_json"
run_expect "malformed manifest json" 1 "malformed manifest json" \
  python3 "$VERIFY" "$MALFORMED_JSON"

echo
echo "--- T-BUNDLE-TAMPER-006B: manifest missing hash_algo fails ---"
MISSING_FIELD="$TMPDIR/missing_field.tar"
rewrite_manifest "$VALID" "$MISSING_FIELD" "missing_hash_algo"
run_expect "missing hash_algo" 1 "manifest hash_algo mismatch" \
  python3 "$VERIFY" "$MISSING_FIELD"

echo
echo "--- T-BUNDLE-TAMPER-007: duplicate manifest entry fails ---"
DUP_ENTRY="$TMPDIR/duplicate_entry.tar"
rewrite_manifest "$VALID" "$DUP_ENTRY" "duplicate_entry"
run_expect "duplicate manifest entry" 1 "duplicate manifest path: artifacts/request.txt" \
  python3 "$VERIFY" "$DUP_ENTRY"

echo
echo "Summary: tamper matrix complete"
