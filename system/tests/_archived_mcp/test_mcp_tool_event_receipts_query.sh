#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_receipt_replay_common.sh"
tool_event_receipt_replay_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_tool_event_receipts_query"
RESULT_DIR="out/test_mcp_tool_event_receipts_query_results"
RUNTIME_DIR="$TMP_ROOT/runtime"
tool_event_receipt_replay_reset "$TMP_ROOT" "$RESULT_DIR"

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
run_id = "RID_MCP_TOOL_EVENT_RECEIPTS"


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


params_digest = "sha256:" + hashlib.sha256(b"query-reverse-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"query-reverse-output").hexdigest()
res = rpc(
    {
        "id": "INGEST2",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {
                "name": "INGEST_TOOL_EVENT",
                "params": {
                    "tool_event_version": "v0",
                    "tool_name": "TEST_TOOL_EVENT_QUERY_REV",
                    "tool_params_digest": params_digest,
                    "exit_code": 0,
                    "outputs": [{"name": "stdout", "digest": out_digest, "ref_type": "blob"}],
                    "provenance": {"source_identifier": "TEST_SRC", "extraction_date": "2026-03-06"},
                    "policy_context_used": "DEFAULT",
                },
            },
            "mode": {"require_admissible": True, "dry_run": False, "run_id": run_id},
        },
    }
)
if res.get("executed") is not True:
    raise SystemExit("FAIL:INGEST_EXEC")
digest = str(res.get("ingest_result", {}).get("tool_event_sha256", ""))

query = rpc(
    {
        "id": "QREV",
        "method": "capabilities.tool_event_receipts",
        "params": {"digest": digest},
    }
)
if query.get("POLICY_BYPASS") != "READ_ONLY_QUERY":
    raise SystemExit("FAIL:POLICY_BYPASS")
ids = query.get("receipt_ids")
if not isinstance(ids, list) or ids != sorted(set(ids)):
    raise SystemExit("FAIL:RECEIPT_ID_LIST")
if run_id not in ids:
    raise SystemExit("FAIL:EXPECTED_RECEIPT_ID")

malformed = rpc(
    {
        "id": "QREV_BAD",
        "method": "capabilities.tool_event_receipts",
        "params": {"digest": "sha256:not-a-real-digest"},
    }
)
bad_ids = malformed.get("receipt_ids")
if not isinstance(bad_ids, list) or bad_ids:
    raise SystemExit("FAIL:MALFORMED_DIGEST_SHOULD_RETURN_EMPTY")

malformed_receipt = rpc(
    {
        "id": "QREV_BAD_RECEIPT",
        "method": "capabilities.receipt_tool_events",
        "params": {"receipt_id": "bad receipt id"},
    }
)
bad_forward = malformed_receipt.get("tool_event_digests")
if not isinstance(bad_forward, list) or bad_forward:
    raise SystemExit("FAIL:MALFORMED_RECEIPT_SHOULD_RETURN_EMPTY")

summary = {
    "tool_event_digest": digest,
    "receipt_ids": ids,
    "malformed_receipt_ids": bad_ids,
    "malformed_tool_event_digests": bad_forward,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$RESULT_DIR/run1.json"
R2="$RESULT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

_HASHES="$(tool_event_receipt_replay_require_deterministic_files "$R1" "$R2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

echo "MCP_TOOL_EVENT_RECEIPTS_QUERY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
