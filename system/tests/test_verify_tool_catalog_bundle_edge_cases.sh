#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_verify_tool_catalog_bundle_edge_cases"
OUT_BASE="$TMP_ROOT/base"
OUT_BAD_TOOL_IDS="$TMP_ROOT/bad_tool_ids"
OUT_BAD_REL="$TMP_ROOT/bad_rel"
OUT_MISMATCH_TOOL_SET="$TMP_ROOT/mismatch_tool_set"
OUT_BAD_FILE_SHA="$TMP_ROOT/bad_file_sha"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402

put(root, {
    "tool_name": "verify_edge_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})
PY

OK_EXPORT="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT_BASE")"
tool_catalog_require_contains "$OK_EXPORT" "TOOL_CATALOG_BUNDLE_EXPORT ok=yes reason=OK" "FAIL:EXPORT_BASE"

set +e
BAD_ID_EXPORT="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT_BASE" --tool-id 'bad id')"
RC0=$?
set -e
[[ $RC0 -ne 0 ]] || { echo "FAIL:BAD_ID_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_ID_EXPORT" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_ID_REASON" \
  ok=no reason=TOOL_ID_INVALID bundle_id=NONE manifest_sha256=NONE tool_count=0 signature_present=no

cp -R "$OUT_BASE" "$OUT_BAD_TOOL_IDS"
python3 - "$OUT_BAD_TOOL_IDS/manifest.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
obj["tool_ids"] = ["tool_not_hex_chars"]
p.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

set +e
BAD_TOOL_IDS_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT_BAD_TOOL_IDS")"
RC1=$?
set -e
[[ $RC1 -ne 0 ]] || { echo "FAIL:BAD_TOOL_IDS_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_TOOL_IDS_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_TOOL_IDS_REASON" ok=no reason=MANIFEST_INVALID signature_verified=not_required
tool_catalog_require_kv_present "$BAD_TOOL_IDS_LINE" bundle_id "FAIL:BAD_TOOL_IDS_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$BAD_TOOL_IDS_LINE" manifest_sha256 "FAIL:BAD_TOOL_IDS_MANIFEST_SHA_MISSING"

cp -R "$OUT_BASE" "$OUT_BAD_REL"
python3 - "$OUT_BAD_REL/manifest.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
obj["files"][0]["path"] = "../outside.json"
p.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

set +e
BAD_REL_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT_BAD_REL")"
RC2=$?
set -e
[[ $RC2 -ne 0 ]] || { echo "FAIL:BAD_REL_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_REL_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_REL_REASON" ok=no reason=MANIFEST_INVALID signature_verified=not_required
tool_catalog_require_kv_present "$BAD_REL_LINE" bundle_id "FAIL:BAD_REL_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$BAD_REL_LINE" manifest_sha256 "FAIL:BAD_REL_MANIFEST_SHA_MISSING"

set +e
BAD_FLAG_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT_BASE" --require-signature 2)"
RC3=$?
set -e
[[ $RC3 -ne 0 ]] || { echo "FAIL:BAD_FLAG_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_FLAG_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_FLAG_REASON" \
  ok=no reason=REQUIRE_SIGNATURE_FLAG_INVALID bundle_id=NONE manifest_sha256=NONE signature_verified=not_required

set +e
BAD_DIR_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir ../bad --require-signature 0)"
RC4=$?
set -e
[[ $RC4 -ne 0 ]] || { echo "FAIL:BAD_DIR_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_DIR_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_DIR_REASON" \
  ok=no reason=BUNDLE_DIR_INVALID bundle_id=NONE manifest_sha256=NONE signature_verified=not_required

set +e
MISSING_DIR_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir out/does_not_exist_catalog_bundle --require-signature 0)"
RC5=$?
set -e
[[ $RC5 -ne 0 ]] || { echo "FAIL:MISSING_DIR_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$MISSING_DIR_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:MISSING_DIR_REASON" \
  ok=no reason=BUNDLE_DIR_INVALID bundle_id=NONE manifest_sha256=NONE signature_verified=not_required

cp -R "$OUT_BASE" "$OUT_MISMATCH_TOOL_SET"
python3 - "$OUT_MISMATCH_TOOL_SET/manifest.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
obj["tool_ids"] = ["tool_1111111111111111"]
p.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

set +e
MISMATCH_SET_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT_MISMATCH_TOOL_SET" --require-signature 0)"
RC6=$?
set -e
[[ $RC6 -ne 0 ]] || { echo "FAIL:MISMATCH_SET_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$MISMATCH_SET_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:MISMATCH_SET_REASON" ok=no reason=TOOL_ID_SET_MISMATCH signature_verified=not_required
tool_catalog_require_kv_present "$MISMATCH_SET_LINE" bundle_id "FAIL:MISMATCH_SET_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$MISMATCH_SET_LINE" manifest_sha256 "FAIL:MISMATCH_SET_MANIFEST_SHA_MISSING"

cp -R "$OUT_BASE" "$OUT_BAD_FILE_SHA"
python3 - "$OUT_BAD_FILE_SHA/manifest.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
obj["files"][0]["sha256"] = "sha256:not-a-digest"
p.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
set +e
BAD_FILE_SHA_LINE="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT_BAD_FILE_SHA" --require-signature 0)"
RC7=$?
set -e
[[ $RC7 -ne 0 ]] || { echo "FAIL:BAD_FILE_SHA_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_FILE_SHA_LINE" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_FILE_SHA_REASON" ok=no reason=MANIFEST_INVALID signature_verified=not_required
tool_catalog_require_kv_present "$BAD_FILE_SHA_LINE" bundle_id "FAIL:BAD_FILE_SHA_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$BAD_FILE_SHA_LINE" manifest_sha256 "FAIL:BAD_FILE_SHA_MANIFEST_SHA_MISSING"

SUM1="$TMP_ROOT/sum1.txt"
SUM2="$TMP_ROOT/sum2.txt"
printf '%s\n%s\n%s\n%s\n%s\n%s\n%s\n' "$BAD_TOOL_IDS_LINE" "$BAD_REL_LINE" "$BAD_FLAG_LINE" "$BAD_DIR_LINE" "$MISSING_DIR_LINE" "$MISMATCH_SET_LINE" "$BAD_FILE_SHA_LINE" > "$SUM1"
printf '%s\n%s\n%s\n%s\n%s\n%s\n%s\n' "$BAD_TOOL_IDS_LINE" "$BAD_REL_LINE" "$BAD_FLAG_LINE" "$BAD_DIR_LINE" "$MISSING_DIR_LINE" "$MISMATCH_SET_LINE" "$BAD_FILE_SHA_LINE" > "$SUM2"
_HASHES="$(tool_catalog_require_deterministic_files "$SUM1" "$SUM2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"
tool_catalog_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "VERIFY_TOOL_CATALOG_BUNDLE_EDGE_CASES=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
