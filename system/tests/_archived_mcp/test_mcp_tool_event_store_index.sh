#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_contract_common.sh"
tool_event_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_tool_event_store_index"
OUT_DIR="out/test_mcp_tool_event_store_index_out"
RUNTIME_DIR="$TMP_ROOT/runtime"
rm -rf "$TMP_ROOT" "$OUT_DIR" out/mcp_exec out/mcp_ingest_tool_event
mkdir -p "$TMP_ROOT" "$OUT_DIR"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" out/mcp_exec out/mcp_ingest_tool_event
  mkdir -p "$TMP_ROOT"

  GOV_RUNTIME_DIR="$RUNTIME_DIR" python3 - "$ROOT" "$out_file" "$RUNTIME_DIR" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
runtime_dir = pathlib.Path(sys.argv[3])

params_digest = "sha256:" + hashlib.sha256(b"tool-params").hexdigest()
output_digest = "sha256:" + hashlib.sha256(b"tool-output").hexdigest()

valid_req = {
    "id": "TOOL_EVENT_STORE_VALID",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_EVENT",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": output_digest, "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_INDEX"},
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(valid_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:VALID_RPC_RC")
valid = json.loads(proc.stdout.strip())["result"]
if valid.get("executed") is not True or valid.get("reason_token") != "OK":
    raise SystemExit("FAIL:VALID_EXECUTION")

idx_path = runtime_dir / "TOOL_EVENTS" / "index.v1.json"
if not idx_path.is_file():
    raise SystemExit("FAIL:INDEX_MISSING")
idx = json.loads(idx_path.read_text(encoding="utf-8"))
entries = idx.get("entries", [])
if not isinstance(entries, list) or len(entries) != 1:
    raise SystemExit("FAIL:INDEX_ENTRY_COUNT")
row = entries[0]
if row.get("tool_event_digest") != valid["ingest_result"]["tool_event_sha256"]:
    raise SystemExit("FAIL:INDEX_DIGEST_MISMATCH")
if row.get("run_id") != "RID_TOOL_EVENT_INDEX":
    raise SystemExit("FAIL:INDEX_RUN_ID")
if int(row.get("stored_seq", 0)) != 1:
    raise SystemExit("FAIL:INDEX_SEQ")
if valid.get("ingest_result", {}).get("TOOL_EVENT_STORE_COLLISION") != "NO":
    raise SystemExit("FAIL:COLLISION_TOKEN")

invalid_req = {
    "id": "TOOL_EVENT_STORE_INVALID",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "INGEST_TOOL_EVENT",
            "params": {
                "tool_event_version": "v0",
                "tool_name": "TEST_TOOL_EVENT",
                "tool_params_digest": params_digest,
                "exit_code": 0,
                "outputs": [{"name": "stdout", "digest": "sha256:xyz", "ref_type": "blob"}],
                "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                "policy_context_used": "DEFAULT",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_TOOL_EVENT_BAD"},
    },
}
proc_bad = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(invalid_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc_bad.returncode != 0:
    raise SystemExit("FAIL:INVALID_RPC_RC")
bad = json.loads(proc_bad.stdout.strip())["result"]
if bad.get("executed") is not False:
    raise SystemExit("FAIL:INVALID_EXECUTED")
if bad.get("reason_token") not in ("TOOL_EVENT_SCHEMA_INVALID", "TOOL_EVENT_DIGEST_INVALID"):
    raise SystemExit("FAIL:INVALID_TOKEN")

idx2 = json.loads(idx_path.read_text(encoding="utf-8"))
entries2 = idx2.get("entries", [])
if len(entries2) != 1:
    raise SystemExit("FAIL:INDEX_MUTATED_BY_INVALID")

summary = {
    "digest": row.get("tool_event_digest", ""),
    "invalid_reason": bad.get("reason_token", ""),
    "stored_seq": int(row.get("stored_seq", 0)),
    "collision_token": valid.get("ingest_result", {}).get("TOOL_EVENT_STORE_COLLISION", ""),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$OUT_DIR/run1.json"
R2="$OUT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(tool_event_sha256_file "$R1")"
H2="$(tool_event_sha256_file "$R2")"
tool_event_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "MCP_TOOL_EVENT_STORE_INDEX=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
