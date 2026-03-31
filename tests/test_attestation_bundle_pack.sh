#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="$ROOT/scripts/attest/bundle.py"
FIXTURE_DIR="$ROOT/tests/fixtures/attestation_bundle/sample"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task110-bundle.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

OUT1="$TMPDIR_LOCAL/bundle1.tar"
OUT2="$TMPDIR_LOCAL/bundle2.tar"
LOG1="$TMPDIR_LOCAL/run1.log"
LOG2="$TMPDIR_LOCAL/run2.log"

python3 "$BUNDLE" pack --input-dir "$FIXTURE_DIR" --out "$OUT1" | tee "$LOG1"
python3 "$BUNDLE" pack --input-dir "$FIXTURE_DIR" --out "$OUT2" | tee "$LOG2"

SHA1="$(python3 - <<'PY' "$OUT1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)"
SHA2="$(python3 - <<'PY' "$OUT2"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)"

[[ "$SHA1" == "$SHA2" ]]

echo "BUNDLE_SHA256_RUN1=$SHA1"
echo "BUNDLE_SHA256_RUN2=$SHA2"
echo "PASS: bundle bytes deterministic across two runs"

python3 - <<'PY' "$OUT1"
import io, json, sys, tarfile
p = sys.argv[1]
with tarfile.open(p, 'r:') as tf:
    names = tf.getnames()
    assert names == sorted(names), f"archive member order not sorted: {names}"
    assert 'manifest.json' in names, 'missing manifest.json'
    assert 'payload/record.json' in names, 'missing payload/record.json'
    assert 'payload/artifacts/request.txt' in names, 'missing request artifact'
    assert 'payload/artifacts/response.txt' in names, 'missing response artifact'
    assert 'payload/artifacts/replay_audit_report.json' in names, 'missing replay audit artifact'
    m = json.load(tf.extractfile('manifest.json'))
    file_paths = [x['path'] for x in m['files']]
    assert file_paths == sorted(file_paths), f'manifest file order not sorted: {file_paths}'
    assert file_paths == ['artifacts/replay_audit_report.json','artifacts/request.txt','artifacts/response.txt','record.json'], file_paths
    assert m['hash_algo'] == 'sha256', m['hash_algo']
    assert m['bundle_version'] == 'attestation_bundle_v1', m['bundle_version']
print('PASS: bundle contains expected files + deterministic manifest')
PY
