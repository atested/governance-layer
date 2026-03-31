#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_tool_catalog_negative_matrix"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import get, list_recent, put  # noqa: E402

tid = put(root, {
    "tool_name": "neg_matrix_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1},
    "declared_capabilities": ["FS_COPY"],
    "created_from": "manual",
})

if get(root, "tool_") is not None:
    raise SystemExit("FAIL:GET_SHORT_ID")
if get(root, "tool_0123456789abcdeg") is not None:
    raise SystemExit("FAIL:GET_NON_HEX")
if get(root, "tool_0123456789abcdef/../x") is not None:
    raise SystemExit("FAIL:GET_PATH_INJECTION")

one = list_recent(root, limit=0)
if len(one) != 1 or str(one[0].get("tool_id", "")) != tid:
    raise SystemExit("FAIL:LIST_LIMIT_ZERO_CLAMP")

defaulted = list_recent(root, limit="bogus")
if len(defaulted) != 1 or str(defaulted[0].get("tool_id", "")) != tid:
    raise SystemExit("FAIL:LIST_LIMIT_INVALID_FALLBACK")

print("NEG_MATRIX=PASS")
PY

set +e
INVALID_ID_LINE="$(python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$TMP_ROOT/out" --tool-id invalid_tool_id)"
INVALID_ID_RC=$?
set -e
[[ $INVALID_ID_RC -ne 0 ]] || { echo "FAIL:INVALID_ID_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$INVALID_ID_LINE" "TOOL_CATALOG_BUNDLE_EXPORT " "FAIL:INVALID_ID_REASON" \
  ok=no reason=TOOL_ID_INVALID bundle_id=NONE manifest_sha256=NONE tool_count=0 signature_present=no

echo "TOOL_CATALOG_NEGATIVE_MATRIX=PASS"
