#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK="$ROOT/scripts/attest/bundle.py"
VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
FIXTURE_DIR="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task111-bundle.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

VALID="$TMPDIR_LOCAL/valid.tar"
TAMPERED="$TMPDIR_LOCAL/tampered.tar"
EXTRA="$TMPDIR_LOCAL/extra.tar"

python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$VALID" >/dev/null

# Create tampered bundle by modifying payload/artifacts/request.txt while preserving member names.
python3 - <<'PY' "$VALID" "$TAMPERED"
import io, tarfile, sys
src, dst = sys.argv[1], sys.argv[2]
with tarfile.open(src, 'r:') as tin, tarfile.open(dst, 'w:', format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        if not m.isfile():
            continue
        f = tin.extractfile(m)
        data = f.read() if f else b''
        if m.name == 'payload/artifacts/request.txt':
            data = b'TAMPERED request body\n'
            m = tarfile.TarInfo(m.name)
            m.size = len(data)
            m.mtime = 0; m.uid = 0; m.gid = 0; m.uname=''; m.gname=''; m.mode = 0o644
        tout.addfile(m, io.BytesIO(data))
PY

# Create extra-file bundle by adding payload/artifacts/extra.txt not declared in manifest.
python3 - <<'PY' "$VALID" "$EXTRA"
import io, tarfile, sys
src, dst = sys.argv[1], sys.argv[2]
with tarfile.open(src, 'r:') as tin, tarfile.open(dst, 'w:', format=tarfile.USTAR_FORMAT) as tout:
    for m in tin.getmembers():
        if not m.isfile():
            continue
        f = tin.extractfile(m)
        data = f.read() if f else b''
        tout.addfile(m, io.BytesIO(data))
    data = b'extra file\n'
    m = tarfile.TarInfo('payload/artifacts/extra.txt')
    m.size = len(data)
    m.mtime = 0; m.uid = 0; m.gid = 0; m.uname=''; m.gname=''; m.mode = 0o644
    tout.addfile(m, io.BytesIO(data))
PY

echo '--- T-BUNDLE-VERIFY-001: valid bundle passes ---'
python3 "$VERIFY" "$VALID"

echo
echo '--- T-BUNDLE-VERIFY-002: tampered payload fails ---'
set +e
out2="$(python3 "$VERIFY" "$TAMPERED" 2>&1)"
rc2=$?
set -e
echo "$out2"
[[ "$rc2" -ne 0 ]]
echo "PASS: tampered bundle rejected (exit=$rc2)"

echo
echo '--- T-BUNDLE-VERIFY-003: extra payload file fails ---'
set +e
out3="$(python3 "$VERIFY" "$EXTRA" 2>&1)"
rc3=$?
set -e
echo "$out3"
[[ "$rc3" -ne 0 ]]
echo "PASS: extra-file bundle rejected (exit=$rc3)"
