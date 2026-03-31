#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_check_bundle_schema_compat"
attest_reset_work_dir "$WORK_DIR"

cat > "$WORK_DIR/a.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha256","files":[]}
JSON
cat > "$WORK_DIR/b.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha256","files":[{"path":"x","sha256":"sha256:111"}]}
JSON
cat > "$WORK_DIR/v_mismatch.json" <<'JSON'
{"bundle_version":"v2","hash_algo":"sha256","files":[]}
JSON
cat > "$WORK_DIR/a_mismatch.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha512","files":[]}
JSON
cat > "$WORK_DIR/missing_version.json" <<'JSON'
{"hash_algo":"sha256","files":[]}
JSON
printf '{"broken":' > "$WORK_DIR/bad.json"

python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b.json" > "$WORK_DIR/run1.json"
python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/b.json" > "$WORK_DIR/run2.json"
_HASHES="$(attest_require_deterministic_files "$WORK_DIR/run1.json" "$WORK_DIR/run2.json" "CHECK_BUNDLE_SCHEMA_COMPAT=FAIL")"
sha1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
sha2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

python3 - "$WORK_DIR/run1.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['compatibility']=='compatible'
assert obj['reason']=='SCHEMA_COMPATIBLE'
PY

python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/v_mismatch.json" > "$WORK_DIR/vout.json"
python3 - "$WORK_DIR/vout.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['compatibility']=='incompatible'
assert obj['reason']=='BUNDLE_VERSION_MISMATCH'
PY

python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/a_mismatch.json" > "$WORK_DIR/aout.json"
python3 - "$WORK_DIR/aout.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['compatibility']=='incompatible'
assert obj['reason']=='HASH_ALGO_MISMATCH'
PY

python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/missing_version.json" > "$WORK_DIR/missing_version_out.json"
python3 - "$WORK_DIR/missing_version_out.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['compatibility']=='incompatible'
assert obj['reason']=='BUNDLE_VERSION_MISSING'
PY

if python3 "$ROOT_DIR/scripts/attest/check_bundle_schema_compat.py" --left "$WORK_DIR/a.json" --right "$WORK_DIR/bad.json" > "$WORK_DIR/malformed_out.json" 2>/dev/null; then
  echo "CHECK_BUNDLE_SCHEMA_COMPAT=FAIL"
  exit 1
fi
python3 - "$WORK_DIR/malformed_out.json" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['kind']=='bundle_schema_compat_v1'
assert obj['compatibility']=='malformed'
assert obj['reason']=='MANIFEST_INVALID'
PY

echo "CHECK_BUNDLE_SCHEMA_COMPAT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
