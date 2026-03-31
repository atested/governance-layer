#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_index_attestation_artifacts"
attest_reset_work_dir "$WORK_DIR"
mkdir -p "$WORK_DIR/input/sub"

printf 'alpha\n' > "$WORK_DIR/input/a.txt"
printf 'beta\n' > "$WORK_DIR/input/sub/b.txt"
cat > "$WORK_DIR/input/manifest.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha256","files":[]}
JSON

python3 "$ROOT_DIR/scripts/attest/index_attestation_artifacts.py" --input "$WORK_DIR/input" > "$WORK_DIR/run1.json"
python3 "$ROOT_DIR/scripts/attest/index_attestation_artifacts.py" --input "$WORK_DIR/input" > "$WORK_DIR/run2.json"
sha1="$(attest_sha256_file "$WORK_DIR/run1.json")"
sha2="$(attest_sha256_file "$WORK_DIR/run2.json")"
attest_require_equal "$sha1" "$sha2" "INDEX_ATTESTATION_ARTIFACTS=FAIL"

python3 - "$WORK_DIR/run1.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['ok'] is True
assert obj['artifact_count'] == 3
paths=[x['path'] for x in obj['artifacts']]
assert paths == sorted(paths)
assert 'manifest.json' in paths
PY

mkdir -p "$WORK_DIR/empty"
if python3 "$ROOT_DIR/scripts/attest/index_attestation_artifacts.py" --input "$WORK_DIR/empty" > "$WORK_DIR/empty_out.json" 2>/dev/null; then
  echo "INDEX_ATTESTATION_ARTIFACTS=FAIL"
  exit 1
fi
python3 - "$WORK_DIR/empty_out.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['kind']=='attestation_artifact_index_v1'
assert obj['reason']=='EMPTY_ARTIFACT_SET'
PY

mkdir -p "$WORK_DIR/invalid_manifest"
printf 'x' > "$WORK_DIR/invalid_manifest/a.txt"
printf '{"broken":' > "$WORK_DIR/invalid_manifest/manifest.json"
if python3 "$ROOT_DIR/scripts/attest/index_attestation_artifacts.py" --input "$WORK_DIR/invalid_manifest" > "$WORK_DIR/invalid_out.json" 2>/dev/null; then
  echo "INDEX_ATTESTATION_ARTIFACTS=FAIL"
  exit 1
fi
python3 - "$WORK_DIR/invalid_out.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['kind']=='attestation_artifact_index_v1'
assert obj['reason']=='MANIFEST_INVALID'
PY

echo "INDEX_ATTESTATION_ARTIFACTS=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
