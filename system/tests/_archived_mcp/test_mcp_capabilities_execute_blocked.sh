#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_blocked"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures"
printf 'blocked\n' > "$TMP_ROOT/fixtures/src.txt"

run_once() {
  local out_file="$1"
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

cases = [
    ("HOT_FILE_TARGET", "FS_MOVE", {"src_path": "out/test_mcp_capabilities_execute_blocked/fixtures/src.txt", "dst_path": "system/scripts/release-gate.sh"}, "TARGET_IS_HOT_FILE"),
    ("TRAVERSAL_TARGET", "FS_MOVE", {"src_path": "out/test_mcp_capabilities_execute_blocked/fixtures/../src.txt", "dst_path": "out/test_mcp_capabilities_execute_blocked/fixtures/dst.txt"}, "PATH_TRAVERSAL"),
]

rows = []
for case_id, cap_name, cap_params, expected_token in cases:
    req = {
        "id": case_id,
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": cap_name, "params": cap_params},
            "mode": {"require_admissible": True, "dry_run": False, "run_id": f"EXEC_BLOCKED_{case_id}"},
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
        raise SystemExit(f"FAIL:RC:{case_id}")
    payload = json.loads(proc.stdout.strip())["result"]
    if payload.get("executed") is not False:
        raise SystemExit(f"FAIL:EXECUTED_UNEXPECTED:{case_id}")
    if payload.get("admissible") is not False:
        raise SystemExit(f"FAIL:ADMISSIBLE_UNEXPECTED:{case_id}")
    got_token = payload.get("reason_token")
    if got_token != expected_token:
        raise SystemExit(f"FAIL:BAD_TOKEN:{case_id}:{got_token}:{expected_token}")
    if "action_record_digest" not in payload:
        raise SystemExit(f"FAIL:NO_DIGEST:{case_id}")
    rows.append(
        {
            "case": case_id,
            "reason_token": got_token,
            "digest": payload["action_record_digest"],
        }
    )

rows.sort(key=lambda r: r["case"])
out_file.write_text(json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_EXECUTE_BLOCKED=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
