#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_receipt_replay_common.sh"
tool_event_receipt_replay_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_replay_check_includes_tool_event_digests"
RESULT_DIR="out/test_mcp_replay_check_includes_tool_event_digests_results"
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
run_id = "RID_REPLAY_TOOL_EVENT_DIGESTS"


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


params_digest = "sha256:" + hashlib.sha256(b"replay-linkage-params").hexdigest()
out_digest = "sha256:" + hashlib.sha256(b"replay-linkage-output").hexdigest()
res = rpc(
    {
        "id": "INGEST_REPLAY",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {
                "name": "INGEST_TOOL_EVENT",
                "params": {
                    "tool_event_version": "v0",
                    "tool_name": "TEST_REPLAY_TOOL_EVENT_DIGESTS",
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
expected_digest = str(res.get("ingest_result", {}).get("tool_event_sha256", ""))

replay = rpc(
    {
        "id": "REPLAY_EMIT",
        "method": "capabilities.replay_check",
        "params": {"run_id": run_id, "emit_artifact": True, "policy_context": "DEFAULT"},
    }
)
if replay.get("admissible_now") is not True:
    raise SystemExit("FAIL:REPLAY_NOT_ADMISSIBLE")

artifact_path = root / "out" / "mcp_exec" / run_id / "replay_check.v0.json"
if not artifact_path.is_file():
    raise SystemExit("FAIL:ARTIFACT_MISSING")
artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
digests = artifact.get("tool_event_digests")
if not isinstance(digests, list) or digests != sorted(set(digests)):
    raise SystemExit("FAIL:TOOL_EVENT_DIGESTS_FIELD")
if expected_digest not in digests:
    raise SystemExit("FAIL:MISSING_EXPECTED_DIGEST")

summary = {
    "run_id": run_id,
    "tool_event_digests": digests,
    "expected_digest": expected_digest,
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

R1="$RESULT_DIR/run1.json"
R2="$RESULT_DIR/run2.json"
run_once "$R1"
run_once "$R2"

H1="$(tool_event_sha256_file "$R1")"
H2="$(tool_event_sha256_file "$R2")"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_REPLAY_CHECK_INCLUDES_TOOL_EVENT_DIGESTS=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
