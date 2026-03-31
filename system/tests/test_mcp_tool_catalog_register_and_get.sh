#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_catalog_register_and_get"
OUT_SUM="$TMP_ROOT/out"
rm -rf "$TMP_ROOT" out/mcp_tool_catalog
mkdir -p "$OUT_SUM"

python3 - "$ROOT" "$OUT_SUM" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_sum = pathlib.Path(sys.argv[2])

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

schema = {"input": {"type": "object"}, "output": {"type": "object"}, "version": "v1"}
res_register = rpc(
    {
        "id": "REG1",
        "method": "capabilities.tool_register",
        "params": {
            "action": {
                "tool_name": "tool_catalog_demo",
                "tool_version": "1.0.0",
                "schema_json": schema,
                "declared_capabilities": ["FS_COPY", "FS_MOVE"],
                "created_from": "external",
            }
        },
    }
)
if res_register.get("executed") is not True:
    raise SystemExit("FAIL:REGISTER_NOT_EXECUTED")
tool_id = str(res_register.get("tool_id", ""))
if not tool_id.startswith("tool_"):
    raise SystemExit("FAIL:TOOL_ID_INVALID")

expected_schema_sha = hashlib.sha256(
    (json.dumps(schema, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
).hexdigest()
if str(res_register.get("schema_sha256", "")) != expected_schema_sha:
    raise SystemExit("FAIL:SCHEMA_SHA_MISMATCH")

res_get = rpc(
    {
        "id": "GET1",
        "method": "capabilities.tool_get",
        "params": {"tool_id": tool_id},
    }
)
if res_get.get("ok") is not True:
    raise SystemExit("FAIL:GET_NOT_OK")
if res_get.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:BYPASS_TOKEN_MISSING")
tool_doc = res_get.get("tool_doc", {})
if str(tool_doc.get("tool_id", "")) != tool_id:
    raise SystemExit("FAIL:TOOL_ID_GET_MISMATCH")
if str(tool_doc.get("schema_sha256", "")) != expected_schema_sha:
    raise SystemExit("FAIL:TOOL_DOC_SCHEMA_SHA_MISMATCH")

summary = {
    "tool_id": tool_id,
    "schema_sha256": expected_schema_sha,
    "register_reason": res_register.get("reason_token"),
    "get_reason": res_get.get("reason_token"),
}
out_sum.mkdir(parents=True, exist_ok=True)
(out_sum / "summary.json").write_text(
    json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
print("MCP_TOOL_CATALOG_REGISTER_AND_GET=PASS")
print(f"TOOL_ID={tool_id}")
print(f"SCHEMA_SHA256={expected_schema_sha}")
PY

echo "CASE=MCP_TOOL_CATALOG_REGISTER_AND_GET PASS"
