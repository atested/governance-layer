#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attest_contract_common.sh"
attest_repo_root "${BASH_SOURCE[0]}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/out/test_canonicalize_manifest"
attest_reset_work_dir "$WORK_DIR"

cat > "$WORK_DIR/input.json" <<'JSON'
{
  "z": 2,
  "a": [
    {"k": 2, "j": 1},
    {"j": 0, "k": 0}
  ],
  "b": {"d": 4, "c": 3}
}
JSON

python3 "$ROOT_DIR/scripts/attest/canonicalize_manifest.py" --input "$WORK_DIR/input.json" > "$WORK_DIR/run1.json"
python3 "$ROOT_DIR/scripts/attest/canonicalize_manifest.py" --input "$WORK_DIR/input.json" > "$WORK_DIR/run2.json"

_HASHES="$(attest_require_deterministic_files "$WORK_DIR/run1.json" "$WORK_DIR/run2.json" "CANONICALIZE_MANIFEST=FAIL")"
sha1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
sha2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

python3 - "$WORK_DIR/run1.json" <<'PY'
import json
import sys
p = sys.argv[1]
obj = json.load(open(p, encoding='utf-8'))
assert obj["ok"] is True
assert obj["kind"] == "manifest_canonical_v1"
assert "canonical_sha256" in obj and obj["canonical_sha256"].startswith("sha256:")
assert list(obj["canonical"].keys()) == ["a", "b", "z"]
PY

printf '{"oops":' > "$WORK_DIR/bad.json"
if python3 "$ROOT_DIR/scripts/attest/canonicalize_manifest.py" --input "$WORK_DIR/bad.json" > "$WORK_DIR/bad_out.json" 2>/dev/null; then
  echo "CANONICALIZE_MANIFEST=FAIL"
  echo "NEGATIVE_CONTROL=MALFORMED_EXPECTED_FAIL"
  exit 1
fi
python3 - "$WORK_DIR/bad_out.json" <<'PY'
import json
import sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
assert obj["ok"] is False
assert obj["kind"] == "manifest_canonical_v1"
assert obj["reason"] == "MANIFEST_INVALID"
PY

echo "CANONICALIZE_MANIFEST=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$sha1"
echo "RUN2_SHA256=$sha2"
