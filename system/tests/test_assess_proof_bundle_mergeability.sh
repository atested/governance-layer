#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_assess_proof_bundle_mergeability"
attest_reset_work_dir "$WORK_DIR"

mk() {
  local path="$1"
  local version="$2"
  local algo="$3"
  local files="$4"
  cat > "$path" <<JSON
{"bundle_version":"$version","hash_algo":"$algo","files":$files}
JSON
}

mk "$WORK_DIR/a.json" "v1" "sha256" '[{"path":"a.txt","sha256":"sha256:111"}]'
mk "$WORK_DIR/b_compatible.json" "v1" "sha256" '[{"path":"a.txt","sha256":"sha256:111"},{"path":"b.txt","sha256":"sha256:222"}]'
mk "$WORK_DIR/b_conflict.json" "v1" "sha256" '[{"path":"a.txt","sha256":"sha256:999"}]'
mk "$WORK_DIR/b_incompat.json" "v2" "sha256" '[{"path":"a.txt","sha256":"sha256:111"}]'
printf '{"broken":' > "$WORK_DIR/bad.json"

python3 "$ROOT_DIR/scripts/attest/assess_proof_bundle_mergeability.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b_compatible.json" > "$WORK_DIR/run1.json"
python3 "$ROOT_DIR/scripts/attest/assess_proof_bundle_mergeability.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b_compatible.json" > "$WORK_DIR/run2.json"

_HASHES="$(attest_require_deterministic_files "$WORK_DIR/run1.json" "$WORK_DIR/run2.json" "ASSESS_PROOF_BUNDLE_MERGEABILITY=FAIL")"
sha1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
sha2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

python3 - "$WORK_DIR/run1.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['mergeability']=='compatible'
assert obj['reason']=='NO_CONFLICTING_DIGESTS'
PY

python3 "$ROOT_DIR/scripts/attest/assess_proof_bundle_mergeability.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b_conflict.json" > "$WORK_DIR/conflict.json"
python3 - "$WORK_DIR/conflict.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['mergeability']=='incompatible'
assert obj['reason']=='CONFLICTING_DIGESTS'
PY

python3 "$ROOT_DIR/scripts/attest/assess_proof_bundle_mergeability.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b_incompat.json" > "$WORK_DIR/incompat.json"
python3 - "$WORK_DIR/incompat.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['mergeability']=='incompatible'
assert obj['reason']=='BUNDLE_VERSION_MISMATCH'
PY

if python3 "$ROOT_DIR/scripts/attest/assess_proof_bundle_mergeability.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/bad.json" > "$WORK_DIR/malformed.json" 2>/dev/null; then
  echo "ASSESS_PROOF_BUNDLE_MERGEABILITY=FAIL"
  exit 1
fi
python3 - "$WORK_DIR/malformed.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['kind']=='proof_bundle_mergeability_v1'
assert obj['mergeability']=='malformed'
assert obj['reason']=='MANIFEST_INVALID'
PY

echo "ASSESS_PROOF_BUNDLE_MERGEABILITY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
