#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_event_receipt_replay_common.sh"
tool_event_receipt_replay_repo_root "${BASH_SOURCE[0]}"
ROOT="$(pwd)"

TMP_ROOT="out/test_mcp_replay_check"
RESULT_DIR="out/test_mcp_replay_check_results"
tool_event_receipt_replay_reset "$TMP_ROOT" "$RESULT_DIR"
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures" out/mcp_exec
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'replay\n' > "$TMP_ROOT/fixtures/src.txt"

  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

exec_req = {
    "id": "REPLAY_EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_replay_check/fixtures/src.txt",
                "dst_path": "out/test_mcp_replay_check/fixtures/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_REPLAY_OK"},
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(exec_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXEC_RC")

replay_req = {"id": "REPLAY_GOOD", "method": "capabilities.replay_check", "params": {"run_id": "RID_REPLAY_OK"}}
good = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(replay_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if good.returncode != 0:
    raise SystemExit("FAIL:REPLAY_GOOD_RC")
good_payload = json.loads(good.stdout.strip())["result"]
if good_payload.get("digest_valid") is not True:
    raise SystemExit("FAIL:REPLAY_GOOD_DIGEST")
if good_payload.get("admissible_now") is not True:
    raise SystemExit("FAIL:REPLAY_GOOD_ADMISSIBLE")

# Tamper one byte in action_record to force digest mismatch.
rec_path = root / "out/mcp_exec/RID_REPLAY_OK/action_record.json"
body = rec_path.read_text(encoding="utf-8")
tampered = body.replace('"NONE"', '"TAMPERED"', 1)
rec_path.write_text(tampered, encoding="utf-8")

bad_req = {"id": "REPLAY_BAD", "method": "capabilities.replay_check", "params": {"run_id": "RID_REPLAY_OK"}}
bad = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(bad_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if bad.returncode != 0:
    raise SystemExit("FAIL:REPLAY_BAD_RC")
bad_payload = json.loads(bad.stdout.strip())["result"]
if bad_payload.get("reason_token") != "DIGEST_MISMATCH":
    raise SystemExit("FAIL:REPLAY_BAD_TOKEN")
if bad_payload.get("digest_valid") is not False:
    raise SystemExit("FAIL:REPLAY_BAD_DIGEST_FLAG")

out = {
    "good": {
        "run_id": good_payload.get("run_id"),
        "reason_token": good_payload.get("reason_token"),
        "digest_valid": good_payload.get("digest_valid"),
        "admissible_now": good_payload.get("admissible_now"),
    },
    "bad": {
        "run_id": bad_payload.get("run_id"),
        "reason_token": bad_payload.get("reason_token"),
        "digest_valid": bad_payload.get("digest_valid"),
        "admissible_now": bad_payload.get("admissible_now"),
    },
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(tool_event_sha256_file "$RUN1")"
H2="$(tool_event_sha256_file "$RUN2")"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_REPLAY_CHECK=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
