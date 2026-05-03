#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_fs_move"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

run_once() {
  local run_tag="$1"
  local out_file="$2"
  rm -rf "$TMP_ROOT/fixtures"
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'move\n' > "$TMP_ROOT/fixtures/src_move.txt"
  printf 'copy\n' > "$TMP_ROOT/fixtures/src_copy.txt"

  python3 - "$ROOT" "$run_tag" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
run_tag = sys.argv[2]
out_file = pathlib.Path(sys.argv[3])

cases = [
    ("FS_MOVE", {
        "src_path": "out/test_mcp_capabilities_execute_fs_move/fixtures/src_move.txt",
        "dst_path": "out/test_mcp_capabilities_execute_fs_move/fixtures/dst_move.txt",
        "overwrite": False,
    }),
    ("FS_COPY", {
        "src_path": "out/test_mcp_capabilities_execute_fs_move/fixtures/src_copy.txt",
        "dst_path": "out/test_mcp_capabilities_execute_fs_move/fixtures/dst_copy.txt",
        "overwrite": False,
    }),
]

rows = []
for cap_name, cap_params in cases:
    req = {
        "id": f"{run_tag}_{cap_name}",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": cap_name, "params": cap_params},
            "mode": {"require_admissible": True, "dry_run": False, "run_id": f"EXEC_MOVE_{run_tag}_{cap_name}"},
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
        raise SystemExit(f"FAIL:RC:{cap_name}")
    payload = json.loads(proc.stdout.strip())["result"]
    if payload.get("executed") is not True:
        raise SystemExit(f"FAIL:NOT_EXECUTED:{cap_name}")
    if payload.get("reason_token") != "NONE":
        raise SystemExit(f"FAIL:BAD_REASON:{cap_name}")
    if "action_record_digest" not in payload:
        raise SystemExit(f"FAIL:NO_DIGEST:{cap_name}")
    rows.append(
        {
            "action_name": payload.get("action_name"),
            "executed": payload.get("executed"),
            "admissible": payload.get("admissible"),
            "reason_token": payload.get("reason_token"),
            "action_record_digest": payload.get("action_record_digest"),
        }
    )

if not (root / "out/test_mcp_capabilities_execute_fs_move/fixtures/dst_move.txt").exists():
    raise SystemExit("FAIL:MOVE_DST_MISSING")
if (root / "out/test_mcp_capabilities_execute_fs_move/fixtures/src_move.txt").exists():
    raise SystemExit("FAIL:MOVE_SRC_EXISTS")
if not (root / "out/test_mcp_capabilities_execute_fs_move/fixtures/dst_copy.txt").exists():
    raise SystemExit("FAIL:COPY_DST_MISSING")
if not (root / "out/test_mcp_capabilities_execute_fs_move/fixtures/src_copy.txt").exists():
    raise SystemExit("FAIL:COPY_SRC_MISSING")

rows.sort(key=lambda r: r["action_name"])
out_file.write_text(json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "A" "$RUN1"
run_once "A" "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_EXECUTE_FS_MOVE_COPY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
