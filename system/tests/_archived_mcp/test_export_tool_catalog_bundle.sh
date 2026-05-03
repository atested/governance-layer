#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_export_tool_catalog_bundle"
OUT1="out/test_export_tool_catalog_bundle_A"
OUT2="out/test_export_tool_catalog_bundle_B"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime
rm -rf "$OUT1" "$OUT2"

python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402
put(root, {
    "tool_name": "export_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "alpha"},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})
put(root, {
    "tool_name": "export_beta",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "beta"},
    "declared_capabilities": ["FS_MOVE"],
    "created_from": "external",
})
PY

R1="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1")"
R2="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT2")"
tool_catalog_require_status_line "$R1" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:EXPORT_LINE_SHAPE" ok=yes reason=OK signature_present=no
tool_catalog_require_status_line "$R2" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:EXPORT_LINE_SHAPE_2" ok=yes reason=OK signature_present=no
tool_catalog_require_kv_equal "$R1" tool_count "2" "FAIL:EXPORT_TOOL_COUNT"
tool_catalog_require_kv_present "$R1" bundle_id "FAIL:EXPORT_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$R1" manifest_sha256 "FAIL:EXPORT_MANIFEST_SHA_MISSING"

[[ -f "$OUT1/manifest.json" ]] || { echo "FAIL:MANIFEST_MISSING"; exit 1; }

python3 - "$OUT1/manifest.json" <<'PY'
import json
import pathlib
import sys
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if manifest.get("bundle_version") != "tool_catalog_bundle_v1":
    raise SystemExit("FAIL:BUNDLE_VERSION")
tool_ids = manifest.get("tool_ids", [])
if not isinstance(tool_ids, list) or tool_ids != sorted(tool_ids):
    raise SystemExit("FAIL:TOOL_IDS_ORDER")
files = manifest.get("files", [])
if not isinstance(files, list) or not files:
    raise SystemExit("FAIL:FILES_MISSING")
paths = [f.get("path") for f in files if isinstance(f, dict)]
if paths != sorted(paths):
    raise SystemExit("FAIL:FILES_ORDER")
PY

_HASHES="$(tool_catalog_require_deterministic_files "$OUT1/manifest.json" "$OUT2/manifest.json" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

set +e
BAD="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1" --sign 2)"
RC=$?
set -e
[[ $RC -ne 0 ]] || { echo "FAIL:BAD_SIGN_FLAG_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_SIGN_REASON" \
  ok=no reason=SIGN_FLAG_INVALID bundle_id=NONE manifest_sha256=NONE tool_count=0 signature_present=no

set +e
BAD_OUT="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir ../bad_out_dir)"
BAD_OUT_RC=$?
set -e
[[ $BAD_OUT_RC -ne 0 ]] || { echo "FAIL:BAD_OUT_DIR_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_OUT" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_OUT_DIR_REASON" \
  ok=no reason=OUT_DIR_INVALID bundle_id=NONE manifest_sha256=NONE tool_count=0 signature_present=no

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
bad_doc = root / "out/mcp_tool_catalog/tools/tool_ffffffffffffffff.json"
bad_doc.parent.mkdir(parents=True, exist_ok=True)
bad_doc.write_text("{bad-json}\n", encoding="utf-8")
idx = root / "out/mcp_tool_catalog/index.v1.json"
doc = json.loads(idx.read_text(encoding="utf-8"))
doc["events"].append({"seq": int(doc.get("next_seq", 1)), "tool_id": "tool_ffffffffffffffff"})
doc["next_seq"] = int(doc.get("next_seq", 1)) + 1
idx.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
set +e
BAD_DOC_LINE="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1" --tool-id tool_ffffffffffffffff)"
BAD_DOC_RC=$?
set -e
[[ $BAD_DOC_RC -ne 0 ]] || { echo "FAIL:BAD_DOC_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_DOC_LINE" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_DOC_REASON" \
  ok=no reason=TOOL_DOC_INVALID bundle_id=NONE manifest_sha256=NONE signature_present=no

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
bad_doc = root / "out/mcp_tool_catalog/tools/tool_eeeeeeeeeeeeeeee.json"
bad_doc.parent.mkdir(parents=True, exist_ok=True)
bad_doc.write_text(
    json.dumps(
        {
            "tool_id": "tool_eeeeeeeeeeeeeeee",
            "schema_json": {"x": 1},
            "schema_sha256": "sha256:not-a-digest",
            "tool_name": "bad_schema_sha",
            "tool_version": "1.0.0",
            "declared_capabilities": [],
            "created_at": "2026-03-09T00:00:00Z",
            "created_from": "manual",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    + "\n",
    encoding="utf-8",
)
idx = root / "out/mcp_tool_catalog/index.v1.json"
doc = json.loads(idx.read_text(encoding="utf-8"))
doc["events"].append({"seq": int(doc.get("next_seq", 1)), "tool_id": "tool_eeeeeeeeeeeeeeee"})
doc["next_seq"] = int(doc.get("next_seq", 1)) + 1
idx.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
set +e
BAD_SCHEMA_SHA_LINE="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1" --tool-id tool_eeeeeeeeeeeeeeee)"
BAD_SCHEMA_SHA_RC=$?
set -e
[[ $BAD_SCHEMA_SHA_RC -ne 0 ]] || { echo "FAIL:BAD_SCHEMA_SHA_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_SCHEMA_SHA_LINE" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_SCHEMA_SHA_REASON" \
  ok=no reason=TOOL_DOC_INVALID bundle_id=NONE manifest_sha256=NONE signature_present=no

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
bad_doc = root / "out/mcp_tool_catalog/tools/tool_dddddddddddddddd.json"
bad_doc.parent.mkdir(parents=True, exist_ok=True)
bad_doc.write_text(
    json.dumps(
        {
            "tool_id": "tool_dddddddddddddddd",
            "schema_json": {"x": 1},
            "schema_sha256": "0" * 64,
            "tool_name": "bad_schema_hash_match",
            "tool_version": "1.0.0",
            "declared_capabilities": ["FS_COPY"],
            "created_from": "manual",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    + "\n",
    encoding="utf-8",
)
idx = root / "out/mcp_tool_catalog/index.v1.json"
doc = json.loads(idx.read_text(encoding="utf-8"))
doc["events"].append({"seq": int(doc.get("next_seq", 1)), "tool_id": "tool_dddddddddddddddd"})
doc["next_seq"] = int(doc.get("next_seq", 1)) + 1
idx.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
set +e
BAD_SCHEMA_MISMATCH_LINE="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1" --tool-id tool_dddddddddddddddd)"
BAD_SCHEMA_MISMATCH_RC=$?
set -e
[[ $BAD_SCHEMA_MISMATCH_RC -ne 0 ]] || { echo "FAIL:BAD_SCHEMA_MISMATCH_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_SCHEMA_MISMATCH_LINE" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:BAD_SCHEMA_MISMATCH_REASON" \
  ok=no reason=TOOL_DOC_INVALID bundle_id=NONE manifest_sha256=NONE signature_present=no

echo "EXPORT_TOOL_CATALOG_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
