#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_diff_proof_bundle"
attest_reset_work_dir "$TMP_ROOT"
mkdir -p "$TMP_ROOT/A" "$TMP_ROOT/B"

cat > "$TMP_ROOT/A/manifest.json" <<'JSON'
{"bundle_version":"attestation_bundle_v1","files":[{"path":"a.txt","sha256":"sha256:1111111111111111111111111111111111111111111111111111111111111111","size":1},{"path":"b.txt","sha256":"sha256:2222222222222222222222222222222222222222222222222222222222222222","size":1}],"hash_algo":"sha256"}
JSON
cat > "$TMP_ROOT/B/manifest.json" <<'JSON'
{"bundle_version":"attestation_bundle_v1","files":[{"path":"a.txt","sha256":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":1},{"path":"c.txt","sha256":"sha256:3333333333333333333333333333333333333333333333333333333333333333","size":1}],"hash_algo":"sha256"}
JSON

OUT="$(python3 scripts/attest/diff_proof_bundle.py --left "$TMP_ROOT/A" --right "$TMP_ROOT/B")"
python3 - "$OUT" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is True
assert obj["kind"] == "proof_bundle_diff_v1"
assert obj["added"] == ["c.txt"]
assert obj["removed"] == ["b.txt"]
assert obj["changed_digests"] == ["a.txt"]
assert obj["unchanged"] == []
assert obj["schema_mismatch"] == []
PY

cat > "$TMP_ROOT/B/bad.json" <<'TXT'
{not-json
TXT
set +e
BAD_OUT="$(python3 scripts/attest/diff_proof_bundle.py --left "$TMP_ROOT/A/manifest.json" --right "$TMP_ROOT/B/bad.json")"
BAD_RC=$?
set -e
[[ $BAD_RC -ne 0 ]] || { echo "FAIL:BAD_SHOULD_FAIL"; exit 1; }
python3 - "$BAD_OUT" <<'PY'
import json
import sys
obj = json.loads(sys.argv[1])
assert obj["ok"] is False
assert obj["kind"] == "proof_bundle_diff_v1"
assert obj["reason"] == "MANIFEST_INVALID"
PY

echo "DIFF_PROOF_BUNDLE=PASS"
