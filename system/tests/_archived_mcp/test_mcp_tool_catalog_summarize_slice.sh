#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_summarize_slice"
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

alpha = register("sum_alpha", "manual", ["FS_COPY", "FS_MOVE"])
beta = register("sum_beta", "manual", ["FS_COPY"])
register("sum_gamma", "external", ["FS_COPY"])

res = rpc(
    {
        "id": "SUM_SLICE",
        "method": "capabilities.tool_catalog_summarize_slice",
        "params": {
            "created_from": "manual",
            "capability": "FS_COPY",
            "limit": 5,
        },
    }
)
if res.get("ok") is not True:
    raise SystemExit("FAIL:SUMMARY_NOT_OK")
if res.get("reason_token") != "OK":
    raise SystemExit("FAIL:SUMMARY_REASON")
if res.get("summary_version") != "tool_catalog_slice_summary_v1":
    raise SystemExit("FAIL:SUMMARY_VERSION")
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
selected_tool_ids = res.get("selected_tool_ids", [])
if selected_tool_ids != [beta, alpha]:
    raise SystemExit("FAIL:SELECTED_TOOL_IDS")
counts = res.get("counts", {})
by_created = counts.get("by_created_from", {})
if int(by_created.get("manual", 0)) != 2:
    raise SystemExit("FAIL:COUNT_BY_CREATED_FROM")
by_cap = counts.get("by_declared_capability", {})
if int(by_cap.get("FS_COPY", 0)) != 2:
    raise SystemExit("FAIL:COUNT_BY_CAPABILITY")
items = res.get("items", [])
if not isinstance(items, list) or len(items) != 2:
    raise SystemExit("FAIL:ITEMS_LEN")
if [str(item.get("tool_id", "")) for item in items] != [beta, alpha]:
    raise SystemExit("FAIL:ITEM_ORDER")

summary = {
    "summary_version": res.get("summary_version"),
    "selected_tool_ids": selected_tool_ids,
    "counts": counts,
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

echo "MCP_TOOL_CATALOG_SUMMARIZE_SLICE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
