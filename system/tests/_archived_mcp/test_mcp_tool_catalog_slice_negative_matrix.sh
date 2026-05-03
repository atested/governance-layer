#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_slice_negative_matrix"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime

python3 - "$ROOT" <<'PY'
import pathlib
import subprocess
import sys
import json

root = pathlib.Path(sys.argv[1])
req = {
    "id": "REG_NEG",
    "method": "capabilities.tool_register",
    "params": {
        "action": {
            "tool_name": "slice_neg_alpha",
            "tool_version": "1.0.0",
            "schema_json": {"v": 1},
            "declared_capabilities": ["FS_COPY"],
            "created_from": "manual",
        }
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:REGISTER_RC")
res = json.loads(proc.stdout.strip())["result"]
if res.get("executed") is not True:
    raise SystemExit("FAIL:REGISTER_NOT_EXECUTED")
PY

python3 - "$ROOT" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])

cases = [
    (
        "LIST_BAD_CREATED",
        "capabilities.tool_catalog_list_slice",
        {"created_from": "bad_source", "capability": "FS_COPY", "limit": 5},
    ),
    (
        "LIST_BAD_CAP",
        "capabilities.tool_catalog_list_slice",
        {"created_from": "any", "capability": "bad cap", "limit": 5},
    ),
    (
        "LIST_BAD_LIMIT",
        "capabilities.tool_catalog_list_slice",
        {"created_from": "any", "capability": "FS_COPY", "limit": "bad"},
    ),
    (
        "SUM_BAD_CREATED",
        "capabilities.tool_catalog_summarize_slice",
        {"created_from": "bad_source", "capability": "FS_COPY", "limit": 5},
    ),
    (
        "SUM_BAD_CAP",
        "capabilities.tool_catalog_summarize_slice",
        {"created_from": "any", "capability": "bad cap", "limit": 5},
    ),
    (
        "SUM_BAD_LIMIT",
        "capabilities.tool_catalog_summarize_slice",
        {"created_from": "any", "capability": "FS_COPY", "limit": "bad"},
    ),
]

for case_id, method, params in cases:
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps({"id": case_id, "method": method, "params": params}, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"FAIL:RPC_RC:{case_id}")
    res = json.loads(proc.stdout.strip())["result"]
    if res.get("ok") is not False:
        raise SystemExit(f"FAIL:EXPECTED_NOT_OK:{case_id}")
    if res.get("reason_token") != "FILTER_INVALID":
        raise SystemExit(f"FAIL:REASON:{case_id}")
    if res.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
        raise SystemExit(f"FAIL:BYPASS:{case_id}")
    if int(res.get("selected_count", -1)) != 0:
        raise SystemExit(f"FAIL:COUNT:{case_id}")
PY

echo "MCP_TOOL_CATALOG_SLICE_NEGATIVE_MATRIX=PASS"
