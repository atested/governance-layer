#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_receipt_replay_common.sh"
tool_event_receipt_replay_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_tool_event_receipt_link_index"
RESULT_DIR="out/test_tool_event_receipt_link_index_results"
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
run_id = "RID_TOOL_EVENT_LINK_INDEX"

sys.path.insert(0, str(root / "mcp"))
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt  # noqa: E402


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


params_digest = "sha256:" + hashlib.sha256(b"tool-link-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"tool-link-output").hexdigest()
res = rpc(
    {
        "id": "INGEST_LINK",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {
                "name": "INGEST_TOOL_EVENT",
                "params": {
                    "tool_event_version": "v0",
                    "tool_name": "TEST_TOOL_EVENT_LINK_INDEX",
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
if not digest.startswith("sha256:"):
    raise SystemExit("FAIL:INGEST_DIGEST")

index_path = root / "out" / "mcp_exec" / "tool_event_links.v1.json"
if not index_path.is_file():
    raise SystemExit("FAIL:LINK_INDEX_MISSING")
index_payload = json.loads(index_path.read_text(encoding="utf-8"))
if index_payload.get("tool_event_link_index_version") != "v1":
    raise SystemExit("FAIL:INDEX_VERSION")

forward = get_tool_events_for_receipt(root, run_id)
if forward != [digest]:
    raise SystemExit("FAIL:FORWARD_LINK")

reverse = get_receipts_for_tool_event(root, digest)
if reverse != [run_id]:
    raise SystemExit("FAIL:REVERSE_LINK")

if get_tool_events_for_receipt(root, "bad receipt id") != []:
    raise SystemExit("FAIL:BAD_RECEIPT_ID_SHOULD_BE_EMPTY")
if get_receipts_for_tool_event(root, "sha256:not-a-real-digest") != []:
    raise SystemExit("FAIL:BAD_DIGEST_SHOULD_BE_EMPTY")

summary = {
    "receipt_id": run_id,
    "tool_event_digest": digest,
    "forward": forward,
    "reverse": reverse,
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

echo "TOOL_EVENT_RECEIPT_LINK_INDEX=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
