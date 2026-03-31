#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_summarize_proof_bundle"
attest_reset_work_dir "$TMP_ROOT"
mkdir -p "$TMP_ROOT/A"

cat > "$TMP_ROOT/A/manifest.json" <<'JSON'
{"bundle_version":"attestation_bundle_v1","files":[{"path":"a.txt","sha256":"sha256:1111111111111111111111111111111111111111111111111111111111111111","size":2},{"path":"b.txt","sha256":"sha256:2222222222222222222222222222222222222222222222222222222222222222","size":3}],"hash_algo":"sha256"}
JSON

O1="$(python3 scripts/attest/summarize_proof_bundle.py --input "$TMP_ROOT/A")"
O2="$(python3 scripts/attest/summarize_proof_bundle.py --input "$TMP_ROOT/A")"

H1="$(printf '%s' "$O1" | shasum -a 256 | awk '{print $1}')"
H2="$(printf '%s' "$O2" | shasum -a 256 | awk '{print $1}')"
attest_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

python3 - "$O1" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is True
assert obj["kind"] == "proof_bundle_summary_v1"
assert obj["file_count"] == 2
assert obj["total_size_bytes"] == 5
assert [x["path"] for x in obj["files"]] == ["a.txt", "b.txt"]
PY

cat > "$TMP_ROOT/bad.json" <<'TXT'
{not-json
TXT
set +e
BAD="$(python3 scripts/attest/summarize_proof_bundle.py --input "$TMP_ROOT/bad.json")"
BAD_RC=$?
set -e
[[ $BAD_RC -ne 0 ]] || { echo "FAIL:BAD_SHOULD_FAIL"; exit 1; }
python3 - "$BAD" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is False
assert obj["kind"] == "proof_bundle_summary_v1"
assert obj["reason"] == "MANIFEST_INVALID"
PY

echo "SUMMARIZE_PROOF_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
