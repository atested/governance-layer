#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_tool_event_query_policy_semantics"
OUT_DIR="out/test_mcp_tool_event_query_policy_semantics_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$OUT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])


def rpc(req):
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


p_digest = "sha256:" + hashlib.sha256(b"policy-params").hexdigest()
o_digest = "sha256:" + hashlib.sha256(b"policy-output").hexdigest()
ingest = rpc(
    {
        "id": "INGEST_POLICY",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {
                "name": "INGEST_TOOL_EVENT",
                "params": {
                    "tool_event_version": "v0",
                    "tool_name": "TEST_TOOL_POLICY",
                    "tool_params_digest": p_digest,
                    "exit_code": 0,
                    "outputs": [{"name": "stdout", "digest": o_digest, "ref_type": "blob"}],
                    "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                    "policy_context_used": "DEFAULT",
                },
            },
            "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_POLICY"},
        },
    }
)
if ingest.get("executed") is not True:
    raise SystemExit("FAIL:INGEST")
digest = str(ingest["ingest_result"]["tool_event_sha256"])
ctx = "STRICT_OUT_ONLY"

get_res = rpc(
    {
        "id": "GET_POLICY",
        "method": "capabilities.tool_event_get",
        "params": {"digest": digest, "policy_context": ctx},
    }
)
recent_res = rpc(
    {
        "id": "RECENT_POLICY",
        "method": "capabilities.tool_event_list_recent",
        "params": {"limit": 1, "policy_context": ctx},
    }
)
receipt_res = rpc(
    {
        "id": "BY_RECEIPT_POLICY",
        "method": "capabilities.tool_event_list_for_receipt",
        "params": {"receipt_id": "RID_TOOL_EVENT_POLICY", "policy_context": ctx},
    }
)

for name, resp in [("get", get_res), ("recent", recent_res), ("receipt", receipt_res)]:
    if resp.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
        raise SystemExit(f"FAIL:{name}:POLICY_BYPASS")
    if resp.get("policy_context_used") != ctx:
        raise SystemExit(f"FAIL:{name}:POLICY_CONTEXT")

summary = {
    "get_ctx": get_res.get("policy_context_used", ""),
    "recent_ctx": recent_res.get("policy_context_used", ""),
    "receipt_ctx": receipt_res.get("policy_context_used", ""),
    "policy_bypass": get_res.get("POLICY_BYPASS", ""),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_TOOL_EVENT_QUERY_POLICY_SEMANTICS=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
