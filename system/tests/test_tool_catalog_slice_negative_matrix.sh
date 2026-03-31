#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_tool_catalog_slice_negative_matrix"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402

put(root, {
    "tool_name": "slice_neg_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})
PY

set +e
BAD_CREATED_LINE="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from bad_source --capability FS_COPY --limit 5 2>/dev/null)"
RC1=$?
set -e
[[ $RC1 -ne 0 ]] || { echo "FAIL:BAD_CREATED_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_CREATED_LINE" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:BAD_CREATED_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_CAP_LINE="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from any --capability 'bad cap' --limit 5 2>/dev/null)"
RC2=$?
set -e
[[ $RC2 -ne 0 ]] || { echo "FAIL:BAD_CAP_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_CAP_LINE" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:BAD_CAP_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_LIMIT_LINE="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from any --capability FS_COPY --limit bad 2>/dev/null)"
RC3=$?
set -e
[[ $RC3 -ne 0 ]] || { echo "FAIL:BAD_LIMIT_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_LIMIT_LINE" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:BAD_LIMIT_REASON" ok=no reason=FILTER_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

set +e
BAD_OUT_LINE="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from any --capability FS_COPY --limit 5 --out-json ../bad.json 2>/dev/null)"
RC4=$?
set -e
[[ $RC4 -ne 0 ]] || { echo "FAIL:BAD_OUT_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD_OUT_LINE" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:BAD_OUT_REASON" ok=no reason=OUT_PATH_INVALID selected_count=0 summary_sha256=NONE report_path=NONE

OK_EMPTY="$(python3 scripts/attest/summarize_tool_catalog_slice.py --created-from external --capability FS_MOVE --limit 5 --out-json out/test_tool_catalog_slice_negative_matrix/empty.json)"
tool_catalog_require_status_line "$OK_EMPTY" "TOOL_CATALOG_SLICE_SUMMARY " "FAIL:OK_EMPTY_REASON" ok=yes reason=OK selected_count=0

echo "TOOL_CATALOG_SLICE_NEGATIVE_MATRIX=PASS"
