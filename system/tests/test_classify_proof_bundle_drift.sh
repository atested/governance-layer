#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_classify_proof_bundle_drift"
attest_reset_work_dir "$WORK_DIR"

mk_manifest() {
  local path="$1"
  local rows="$2"
  cat > "$path" <<JSON
{"bundle_version":"v1","hash_algo":"sha256","files":${rows}}
JSON
}

mk_manifest "$WORK_DIR/base.json" '[{"path":"a.txt","sha256":"sha256:111"}]'
mk_manifest "$WORK_DIR/additive.json" '[{"path":"a.txt","sha256":"sha256:111"},{"path":"b.txt","sha256":"sha256:222"}]'
mk_manifest "$WORK_DIR/subtractive.json" '[]'
mk_manifest "$WORK_DIR/digest_only.json" '[{"path":"a.txt","sha256":"sha256:999"}]'
cat > "$WORK_DIR/structural.json" <<'JSON'
{"bundle_version":"v2","hash_algo":"sha512","files":[{"path":"a.txt","sha256":"sha256:111"},{"path":"x.txt","sha256":"sha256:333"}]}
JSON
printf '{"broken":' > "$WORK_DIR/malformed.json"

python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/base.json" > "$WORK_DIR/unchanged1.json"
python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/base.json" > "$WORK_DIR/unchanged2.json"
_HASHES="$(attest_require_deterministic_files "$WORK_DIR/unchanged1.json" "$WORK_DIR/unchanged2.json" "CLASSIFY_PROOF_BUNDLE_DRIFT=FAIL")"
sha1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
sha2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/additive.json" > "$WORK_DIR/additive_out.json"
python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/subtractive.json" > "$WORK_DIR/subtractive_out.json"
python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/digest_only.json" > "$WORK_DIR/digest_out.json"
python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/structural.json" > "$WORK_DIR/structural_out.json"

python3 - "$WORK_DIR/unchanged1.json" "$WORK_DIR/additive_out.json" "$WORK_DIR/subtractive_out.json" "$WORK_DIR/digest_out.json" "$WORK_DIR/structural_out.json" <<'PY'
import json
import sys
u, a, s, d, st = [json.load(open(p, encoding='utf-8')) for p in sys.argv[1:]]
assert u["category"] == "unchanged" and u["reason"] == "NO_DRIFT"
assert a["category"] == "additive" and a["reason"] == "ADDED_FILES_ONLY"
assert s["category"] == "subtractive" and s["reason"] == "REMOVED_FILES_ONLY"
assert d["category"] == "digest_only" and d["reason"] == "DIGESTS_CHANGED"
assert st["category"] == "structural" and st["reason"] == "SCHEMA_MISMATCH"
PY

if python3 "$ROOT_DIR/scripts/attest/classify_proof_bundle_drift.py" --left "$WORK_DIR/base.json" --right "$WORK_DIR/malformed.json" > "$WORK_DIR/malformed_out.json" 2>/dev/null; then
  echo "CLASSIFY_PROOF_BUNDLE_DRIFT=FAIL"
  echo "NEGATIVE_CONTROL=MALFORMED_EXPECTED_FAIL"
  exit 1
fi
python3 - "$WORK_DIR/malformed_out.json" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj["ok"] is False
assert obj["kind"] == "proof_bundle_drift_v1"
assert obj["category"] == "malformed"
assert obj["reason"] == "MANIFEST_INVALID"
PY

echo "CLASSIFY_PROOF_BUNDLE_DRIFT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
