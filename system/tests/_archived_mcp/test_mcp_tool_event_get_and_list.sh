#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_tool_event_get_and_list"
OUT_DIR="out/test_mcp_tool_event_get_and_list_out"
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


def ingest(run_id: str, suffix: str):
    p_digest = "sha256:" + hashlib.sha256(f"params-{suffix}".encode("utf-8")).hexdigest()
    o_digest = "sha256:" + hashlib.sha256(f"output-{suffix}".encode("utf-8")).hexdigest()
    req = {
        "id": f"INGEST_{suffix}",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {
                "name": "INGEST_TOOL_EVENT",
                "params": {
                    "tool_event_version": "v0",
                    "tool_name": "TEST_TOOL_QUERY",
                    "tool_params_digest": p_digest,
                    "exit_code": 0,
                    "outputs": [{"name": "stdout", "digest": o_digest, "ref_type": "blob"}],
                    "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                    "policy_context_used": "DEFAULT",
                },
            },
            "mode": {"require_admissible": True, "dry_run": False, "run_id": run_id},
        },
    }
    res = rpc(req)
    if res.get("executed") is not True:
        raise SystemExit("FAIL:INGEST_EXEC")
    return str(res["ingest_result"]["tool_event_sha256"])


d1 = ingest("RID_TOOL_EVENT_Q1", "Q1")
d2 = ingest("RID_TOOL_EVENT_Q2", "Q2")

get_res = rpc({"id": "GET1", "method": "capabilities.tool_event_get", "params": {"digest": d1}})
if get_res.get("ok") is not True:
    raise SystemExit("FAIL:GET_NOT_OK")
if get_res.get("tool_event_digest") != d1:
    raise SystemExit("FAIL:GET_DIGEST")
if int(get_res.get("stored_at", 0)) < 1:
    raise SystemExit("FAIL:GET_STORED_AT")

recent = rpc({"id": "RECENT", "method": "capabilities.tool_event_list_recent", "params": {"limit": 2}})
events = recent.get("events", [])
if not isinstance(events, list) or len(events) != 2:
    raise SystemExit("FAIL:RECENT_LEN")
if [e.get("tool_event_digest") for e in events] != [d1, d2]:
    raise SystemExit("FAIL:RECENT_ORDER")

for_receipt = rpc(
    {
        "id": "BY_RECEIPT",
        "method": "capabilities.tool_event_list_for_receipt",
        "params": {"receipt_id": "RID_TOOL_EVENT_Q2"},
    }
)
r_events = for_receipt.get("events", [])
if not isinstance(r_events, list) or len(r_events) != 1:
    raise SystemExit("FAIL:RECEIPT_LEN")
if r_events[0].get("tool_event_digest") != d2:
    raise SystemExit("FAIL:RECEIPT_DIGEST")

summary = {
    "get_digest": get_res.get("tool_event_digest", ""),
    "recent_digests": [e.get("tool_event_digest", "") for e in events],
    "receipt_digest": r_events[0].get("tool_event_digest", ""),
    "stored_at_recent": [int(e.get("stored_at", 0)) for e in events],
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
tool_event_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "MCP_TOOL_EVENT_GET_AND_LIST=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
