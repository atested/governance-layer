#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_list_recent"
OUT_SUM="$TMP_ROOT/out"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog
mkdir -p "$OUT_SUM"

run_once() {
  local out_file="$1"
  rm -rf out/mcp_tool_catalog
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

def register(name: str, version: str) -> str:
    res = rpc(
        {
            "id": f"REG_{name}",
            "method": "capabilities.tool_register",
            "params": {
                "action": {
                    "tool_name": name,
                    "tool_version": version,
                    "schema_json": {"name": name, "version": version},
                    "declared_capabilities": ["FS_MOVE"],
                    "created_from": "manual",
                }
            },
        }
    )
    if res.get("executed") is not True:
        raise SystemExit("FAIL:REGISTER")
    return str(res.get("tool_id", ""))

id1 = register("catalog_tool_one", "1.0.0")
id2 = register("catalog_tool_two", "1.0.0")

recent = rpc(
    {
        "id": "LIST",
        "method": "capabilities.tool_list_recent",
        "params": {"limit": 1},
    }
)
if recent.get("ok") is not True:
    raise SystemExit("FAIL:LIST_NOT_OK")
if recent.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:BYPASS_TOKEN_MISSING")
tools = recent.get("tools", [])
if not isinstance(tools, list) or len(tools) != 1:
    raise SystemExit("FAIL:LIST_SIZE")
top = tools[0]
if str(top.get("tool_id", "")) != id2:
    raise SystemExit("FAIL:ORDERING")

summary = {
    "first_tool_id": id1,
    "latest_tool_id": id2,
    "list_tool_id": str(top.get("tool_id", "")),
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

echo "MCP_TOOL_CATALOG_LIST_RECENT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
