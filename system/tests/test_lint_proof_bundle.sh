#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_lint_proof_bundle"
attest_reset_work_dir "$WORK_DIR"
mkdir -p "$WORK_DIR/ok" "$WORK_DIR/bad"

printf 'alpha\n' > "$WORK_DIR/ok/a.txt"
printf 'beta\n' > "$WORK_DIR/ok/b.txt"
sha_a="$(sha256sum "$WORK_DIR/ok/a.txt" | awk '{print $1}')"
sha_b="$(sha256sum "$WORK_DIR/ok/b.txt" | awk '{print $1}')"

cat > "$WORK_DIR/ok/manifest.json" <<JSON
{"bundle_version":"v1","hash_algo":"sha256","files":[{"path":"a.txt","sha256":"sha256:${sha_a}","size":6},{"path":"b.txt","sha256":"sha256:${sha_b}","size_bytes":5}]}
JSON

python3 "$ROOT_DIR/scripts/attest/lint_proof_bundle.py" --input "$WORK_DIR/ok" > "$WORK_DIR/ok1.json"
python3 "$ROOT_DIR/scripts/attest/lint_proof_bundle.py" --input "$WORK_DIR/ok" > "$WORK_DIR/ok2.json"

_HASHES="$(attest_require_deterministic_files "$WORK_DIR/ok1.json" "$WORK_DIR/ok2.json" "LINT_PROOF_BUNDLE=FAIL")"
sha1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
sha2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

python3 - "$WORK_DIR/ok1.json" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj["ok"] is True
assert obj["reason"] == "OK"
assert obj["file_count"] == 2
assert [r["path"] for r in obj["files"]] == ["a.txt", "b.txt"]
PY

cat > "$WORK_DIR/bad/manifest.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha256","files":[{"path":"dup.txt","sha256":"sha256:abc","size":1},{"path":"dup.txt","sha256":"sha256:def","size":2}]}
JSON
if python3 "$ROOT_DIR/scripts/attest/lint_proof_bundle.py" --input "$WORK_DIR/bad" > "$WORK_DIR/bad_dup.json" 2>/dev/null; then
  echo "LINT_PROOF_BUNDLE=FAIL"
  echo "NEGATIVE_CONTROL=DUPLICATE_PATH_EXPECTED_FAIL"
  exit 1
fi
python3 - "$WORK_DIR/bad_dup.json" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj["ok"] is False
assert obj["kind"] == "proof_bundle_lint_v1"
assert obj["reason"] == "DUPLICATE_PATH"
PY

cat > "$WORK_DIR/missing_files.json" <<'JSON'
{"bundle_version":"v1","hash_algo":"sha256"}
JSON
if python3 "$ROOT_DIR/scripts/attest/lint_proof_bundle.py" --input "$WORK_DIR/missing_files.json" > "$WORK_DIR/bad_missing.json" 2>/dev/null; then
  echo "LINT_PROOF_BUNDLE=FAIL"
  echo "NEGATIVE_CONTROL=INCOMPLETE_EXPECTED_FAIL"
  exit 1
fi
python3 - "$WORK_DIR/bad_missing.json" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj["ok"] is False
assert obj["kind"] == "proof_bundle_lint_v1"
assert obj["reason"] == "FIELD_MISSING"
PY

echo "LINT_PROOF_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
