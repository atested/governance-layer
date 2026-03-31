#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_tool_event_slice_negative_matrix"
RUNTIME_DIR="$TMP_ROOT/runtime"
tool_event_reset_dir "$TMP_ROOT"

GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_event_store import upsert_tool_event_index  # noqa: E402

upsert_tool_event_index(root, "RID_NEG_A", "sha256:" + "a" * 64, "runtime/TOOL_EVENTS/neg_a.json", "runtime/RECEIPTS/neg_a.json")
PY

set +e
BAD_RECEIPT_LINE="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id 'bad receipt' --digest-prefix aaaa --limit 5 2>/dev/null)"
RC1=$?
set -e
[[ $RC1 -ne 0 ]] || { echo "FAIL:BAD_RECEIPT_SHOULD_FAIL"; exit 1; }
tool_event_require_status_line "$BAD_RECEIPT_LINE" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:BAD_RECEIPT_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_PREFIX_LINE="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id any --digest-prefix 'zzzz' --limit 5 2>/dev/null)"
RC2=$?
set -e
[[ $RC2 -ne 0 ]] || { echo "FAIL:BAD_PREFIX_SHOULD_FAIL"; exit 1; }
tool_event_require_status_line "$BAD_PREFIX_LINE" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:BAD_PREFIX_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_LIMIT_LINE="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id any --digest-prefix aaaa --limit bad 2>/dev/null)"
RC3=$?
set -e
[[ $RC3 -ne 0 ]] || { echo "FAIL:BAD_LIMIT_SHOULD_FAIL"; exit 1; }
tool_event_require_status_line "$BAD_LIMIT_LINE" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:BAD_LIMIT_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_OUT_LINE="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id any --digest-prefix aaaa --limit 5 --out-json ../bad.json 2>/dev/null)"
RC4=$?
set -e
[[ $RC4 -ne 0 ]] || { echo "FAIL:BAD_OUT_SHOULD_FAIL"; exit 1; }
tool_event_require_status_line "$BAD_OUT_LINE" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:BAD_OUT_REASON" ok=no reason=OUT_PATH_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

OK_EMPTY="$(GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 scripts/attest/summarize_tool_event_slice.py --receipt-id RID_MISSING --digest-prefix aaaa --limit 5 --out-json out/test_tool_event_slice_negative_matrix/empty.json)"
tool_event_require_status_line "$OK_EMPTY" "TOOL_EVENT_SLICE_SUMMARY " "FAIL:OK_EMPTY_REASON" ok=yes reason=OK selected_count=0

echo "TOOL_EVENT_SLICE_NEGATIVE_MATRIX=PASS"
