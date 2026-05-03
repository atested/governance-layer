#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_tool_event_slice_summary"
OUT1="$TMP_ROOT/run1"
OUT2="$TMP_ROOT/run2"
RUNTIME_DIR="$TMP_ROOT/runtime"
tool_event_reset_dir "$TMP_ROOT"

run_once() {
  local out_dir="$1"
  local out_json="$out_dir/summary.json"
  rm -rf "$out_dir" "$RUNTIME_DIR"
  mkdir -p "$out_dir"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_event_store import upsert_tool_event_index  # noqa: E402

upsert_tool_event_index(root, "RID_SLICE_A", "sha256:" + "1" * 64, "runtime/TOOL_EVENTS/e1.json", "runtime/RECEIPTS/a1.json")
upsert_tool_event_index(root, "RID_SLICE_B", "sha256:" + "2" * 64, "runtime/TOOL_EVENTS/e2.json", "runtime/RECEIPTS/a2.json")
upsert_tool_event_index(root, "RID_SLICE_A", "sha256:" + "3" * 64, "runtime/TOOL_EVENTS/e3.json", "runtime/RECEIPTS/a3.json")
PY

  LINE="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id RID_SLICE_A --digest-prefix 3333 --limit 5 --out-json "$out_json")"
  tool_event_require_status_line "$LINE" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:SUMMARY_LINE" ok=yes reason=OK selected_count=1
  tool_event_require_kv_present "$LINE" summary_sha256 "FAIL:SUMMARY_SHA_MISSING"
  tool_event_require_kv_equal "$LINE" report_path "$out_json" "FAIL:SUMMARY_REPORT_PATH"

  python3 - "$out_json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
if obj.get("summary_version") != "tool_event_slice_summary_v1":
    raise SystemExit("FAIL:SUMMARY_VERSION")
filters = obj.get("filters", {})
if filters.get("receipt_id") != "RID_SLICE_A":
    raise SystemExit("FAIL:FILTER_RECEIPT")
if filters.get("digest_prefix") != "3333":
    raise SystemExit("FAIL:FILTER_PREFIX")
if int(obj.get("selected_count", -1)) != 1:
    raise SystemExit("FAIL:SELECTED_COUNT")
items = obj.get("items", [])
if not isinstance(items, list) or len(items) != 1:
    raise SystemExit("FAIL:ITEMS_LEN")
if items[0].get("receipt_id") != "RID_SLICE_A":
    raise SystemExit("FAIL:ITEM_RECEIPT")
if not str(items[0].get("tool_event_digest", "")).startswith("sha256:3333"):
    raise SystemExit("FAIL:ITEM_PREFIX")
PY
}

run_once "$OUT1"
run_once "$OUT2"

H1="$(tool_event_sha256_file "$OUT1/summary.json")"
H2="$(tool_event_sha256_file "$OUT2/summary.json")"
tool_event_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "TOOL_EVENT_SLICE_SUMMARY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
