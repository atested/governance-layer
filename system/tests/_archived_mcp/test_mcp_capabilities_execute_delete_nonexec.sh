#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_delete_nonexec"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  printf 'plain\n' > "$TMP_ROOT/fixtures/nonexec.txt"
  chmod 0644 "$TMP_ROOT/fixtures/nonexec.txt"

  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

req = {
    "id": "DEL_NONEXEC_ONLY",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_DELETE_NONEXEC",
            "params": {"path": "out/test_mcp_capabilities_execute_delete_nonexec/fixtures/nonexec.txt"},
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "EXEC_DEL_NONEXEC_FIXED"},
    },
}

proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:DEL_NONEXEC_RC")
payload = json.loads(proc.stdout.strip())["result"]
if payload.get("executed") is not True:
    raise SystemExit("FAIL:DEL_NONEXEC_NOT_EXECUTED")
if payload.get("reason_token") != "NONE":
    raise SystemExit("FAIL:DEL_NONEXEC_BAD_REASON")
digest = payload.get("action_record_digest")
if not isinstance(digest, str) or not digest.startswith("sha256:"):
    raise SystemExit("FAIL:DEL_NONEXEC_NO_DIGEST")

target = root / "out/test_mcp_capabilities_execute_delete_nonexec/fixtures/nonexec.txt"
if target.exists():
    raise SystemExit("FAIL:DEL_NONEXEC_FILE_STILL_EXISTS")

out_file.write_text(
    json.dumps(
        {
            "action_name": payload.get("action_name"),
            "executed": payload.get("executed"),
            "admissible": payload.get("admissible"),
            "reason_token": payload.get("reason_token"),
            "action_record_digest": digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    + "\n",
    encoding="utf-8",
)
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_EXECUTE_DELETE_NONEXEC=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
