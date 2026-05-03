#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_list_slice"
OUT_SUM="$TMP_ROOT/out"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog out/mcp_tool_catalog_bundles
mkdir -p "$OUT_SUM"

run_once() {
  local out_file="$1"
  rm -rf out/mcp_tool_catalog out/mcp_tool_catalog_bundles
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

def rpc(req: dict) -> dict:
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:RPC_RC")
    return json.loads(proc.stdout.strip())["result"]

def register(name: str, created_from: str, declared_capabilities: list[str]) -> str:
    res = rpc(
        {
            "id": f"REG_{name}",
            "method": "capabilities.tool_register",
            "params": {
                "action": {
                    "tool_name": name,
                    "tool_version": "1.0.0",
                    "schema_json": {"name": name},
                    "declared_capabilities": declared_capabilities,
                    "created_from": created_from,
                }
            },
        }
    )
    if res.get("executed") is not True:
        raise SystemExit("FAIL:REGISTER")
    return str(res.get("tool_id", ""))

register("slice_alpha", "manual", ["FS_COPY", "FS_MOVE"])
target_id = register("slice_beta", "manual", ["FS_COPY"])
register("slice_gamma", "external", ["FS_COPY"])
register("slice_delta", "manual", ["FS_MOVE"])

res = rpc(
    {
        "id": "LIST_SLICE",
        "method": "capabilities.tool_catalog_list_slice",
        "params": {
            "created_from": "manual",
            "capability": "FS_COPY",
            "limit": 5,
        },
    }
)
if res.get("ok") is not True:
    raise SystemExit("FAIL:LIST_SLICE_NOT_OK")
if res.get("reason_token") != "OK":
    raise SystemExit("FAIL:LIST_SLICE_REASON")
if res.get("tool_catalog_slice_version") != "tool_catalog_slice_v1":
    raise SystemExit("FAIL:SLICE_VERSION")
if res.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:BYPASS_TOKEN_MISSING")
filters = res.get("filters", {})
if filters.get("created_from") != "manual":
    raise SystemExit("FAIL:FILTER_CREATED_FROM")
if filters.get("capability") != "FS_COPY":
    raise SystemExit("FAIL:FILTER_CAPABILITY")
if int(filters.get("limit", 0)) != 5:
    raise SystemExit("FAIL:FILTER_LIMIT")
if int(res.get("selected_count", -1)) != 2:
    raise SystemExit("FAIL:SELECTED_COUNT")
tools = res.get("tools", [])
if not isinstance(tools, list) or len(tools) != 2:
    raise SystemExit("FAIL:TOOLS_LEN")
if str(tools[0].get("tool_id", "")) != target_id:
    raise SystemExit("FAIL:ORDERING")
for row in tools:
    if row.get("created_from") != "manual":
        raise SystemExit("FAIL:ROW_CREATED_FROM")
    if "FS_COPY" not in row.get("declared_capabilities", []):
        raise SystemExit("FAIL:ROW_CAPABILITY")

summary = {
    "selected_count": int(res.get("selected_count", 0)),
    "selected_tool_ids": [str(row.get("tool_id", "")) for row in tools],
    "filters": filters,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_SUM/run1.json"
R2="$OUT_SUM/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_TOOL_CATALOG_LIST_SLICE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
