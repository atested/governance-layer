#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_action_record"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures"
printf 'x\n' > "$TMP_ROOT/fixtures/src.txt"

RUN_ID="AR_FIXED_001"
REC_DIR="out/mcp_exec/$RUN_ID"

python3 - "$ROOT" <<'PY'
import json
import subprocess
import sys

root = sys.argv[1]
req = {
    "id": "EXEC_AR",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_MOVE",
            "params": {
                "src_path": "out/test_mcp_capabilities_execute_action_record/fixtures/src.txt",
                "dst_path": "out/test_mcp_capabilities_execute_action_record/fixtures/dst.txt",
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "AR_FIXED_001"},
    },
}
proc = subprocess.run(
    ["python3", f"{root}/mcp/server.py", "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXEC_RC")
payload = json.loads(proc.stdout.strip()).get("result", {})
if payload.get("executed") is not True:
    raise SystemExit("FAIL:NOT_EXECUTED")
if payload.get("reason_token") != "NONE":
    raise SystemExit("FAIL:BAD_REASON")
if "action_record_digest" not in payload:
    raise SystemExit("FAIL:NO_DIGEST")
print(payload["action_record_digest"])
PY

[[ ! -e "$TMP_ROOT/fixtures/src.txt" ]] || { echo "FAIL:SRC_STILL_EXISTS"; exit 1; }
[[ -e "$TMP_ROOT/fixtures/dst.txt" ]] || { echo "FAIL:DST_MISSING"; exit 1; }
[[ -f "$REC_DIR/action_record.json" ]] || { echo "FAIL:RECORD_MISSING"; exit 1; }
[[ -f "$REC_DIR/action_record.sha256" ]] || { echo "FAIL:DIGEST_FILE_MISSING"; exit 1; }

python3 - "$REC_DIR/action_record.json" "$REC_DIR/action_record.sha256" <<'PY'
import hashlib
import json
import pathlib
import sys

record_path = pathlib.Path(sys.argv[1])
digest_path = pathlib.Path(sys.argv[2])
body = record_path.read_text(encoding="utf-8")
obj = json.loads(body)
assert obj["action_record_version"] == "v0"
assert obj["action_name"] == "FS_MOVE"
assert obj["outcome"] == "EXECUTED"
assert obj["reason_token"] == "NONE"
expected = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
actual = digest_path.read_text(encoding="utf-8").strip()
assert actual == expected
print("MCP_EXECUTE_ACTION_RECORD=PASS")
PY
