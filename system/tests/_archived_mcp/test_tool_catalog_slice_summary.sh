#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_tool_catalog_slice_summary"
OUT1="$TMP_ROOT/run1"
OUT2="$TMP_ROOT/run2"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

run_once() {
  local out_dir="$1"
  local out_json="$out_dir/summary.json"
  rm -rf "$out_dir" out/mcp_tool_catalog out/mcp_tool_catalog_bundles
  mkdir -p "$out_dir"

  python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402

put(root, {
    "tool_name": "slice_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "alpha"},
    "declared_capabilities": ["FS_COPY", "FS_MOVE"],
    "created_from": "manual",
})
put(root, {
    "tool_name": "slice_beta",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "beta"},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "external",
})
put(root, {
    "tool_name": "slice_gamma",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "gamma"},
    "declared_capabilities": ["FS_MOVE"],
    "created_from": "manual",
})
PY

  LINE="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from manual --capability FS_COPY --limit 5 --out-json "$out_json")"
  tool_catalog_require_status_line "$LINE" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:SUMMARY_LINE" ok=yes reason=OK selected_count=1
  tool_catalog_require_kv_present "$LINE" summary_sha256 "FAIL:SUMMARY_SHA_MISSING"
  tool_catalog_require_kv_equal "$LINE" report_path "${out_json}" "FAIL:SUMMARY_REPORT_PATH"

  python3 - "$out_json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
if obj.get("summary_version") != "tool_catalog_slice_summary_v1":
    raise SystemExit("FAIL:SUMMARY_VERSION")
filters = obj.get("filters", {})
if filters.get("created_from") != "manual":
    raise SystemExit("FAIL:FILTER_CREATED_FROM")
if filters.get("capability") != "FS_COPY":
    raise SystemExit("FAIL:FILTER_CAPABILITY")
if int(obj.get("selected_count", -1)) != 1:
    raise SystemExit("FAIL:SELECTED_COUNT")
items = obj.get("items", [])
if not isinstance(items, list) or len(items) != 1:
    raise SystemExit("FAIL:ITEMS_LEN")
if items[0].get("created_from") != "manual":
    raise SystemExit("FAIL:ITEM_CREATED_FROM")
if "FS_COPY" not in items[0].get("declared_capabilities", []):
    raise SystemExit("FAIL:ITEM_CAPABILITY")
PY
}

run_once "$OUT1"
run_once "$OUT2"

H1="$(tool_catalog_sha256_file "$OUT1/summary.json")"
H2="$(tool_catalog_sha256_file "$OUT2/summary.json")"
tool_catalog_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "TOOL_CATALOG_SLICE_SUMMARY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
