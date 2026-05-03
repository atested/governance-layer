#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_receipt_and_list_recent"
rm -rf "$TMP_ROOT" out/mcp_exec
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures" out/mcp_exec
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'a\n' > "$TMP_ROOT/fixtures/a.txt"
  printf 'b\n' > "$TMP_ROOT/fixtures/b.txt"
  printf 'c\n' > "$TMP_ROOT/fixtures/c.txt"

  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

execs = [
    ("RID_03", "FS_MOVE", {"src_path": "out/test_mcp_receipt_and_list_recent/fixtures/a.txt", "dst_path": "out/test_mcp_receipt_and_list_recent/fixtures/a_moved.txt"}),
    ("RID_01", "FS_COPY", {"src_path": "out/test_mcp_receipt_and_list_recent/fixtures/b.txt", "dst_path": "out/test_mcp_receipt_and_list_recent/fixtures/b_copy.txt"}),
    ("RID_02", "FS_DELETE_NONEXEC", {"path": "out/test_mcp_receipt_and_list_recent/fixtures/c.txt"}),
]
for run_id, cap_name, cap_params in execs:
    req = {
        "id": run_id,
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": cap_name, "params": cap_params},
            "mode": {"require_admissible": True, "dry_run": False, "run_id": run_id},
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
        raise SystemExit("FAIL:EXEC_RC")

receipt_req = {"id": "GET1", "method": "capabilities.receipt", "params": {"run_id": "RID_02"}}
receipt_proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(receipt_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if receipt_proc.returncode != 0:
    raise SystemExit("FAIL:RECEIPT_RC")
receipt = json.loads(receipt_proc.stdout.strip())["result"]
if receipt.get("digest_valid") is not True:
    raise SystemExit("FAIL:RECEIPT_DIGEST_INVALID")
if receipt.get("run_id") != "RID_02":
    raise SystemExit("FAIL:RECEIPT_RUN_ID")

list_req = {"id": "LIST1", "method": "capabilities.list_recent", "params": {"limit": 2}}
list_proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(list_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if list_proc.returncode != 0:
    raise SystemExit("FAIL:LIST_RC")
lst = json.loads(list_proc.stdout.strip())["result"]
rows = lst.get("receipts", [])
if len(rows) != 2:
    raise SystemExit("FAIL:LIST_COUNT")
run_ids = [r.get("run_id") for r in rows]
if run_ids != ["RID_02", "RID_03"]:
    raise SystemExit("FAIL:LIST_ORDER")

out = {
    "receipt": {
        "run_id": receipt.get("run_id"),
        "digest": receipt.get("digest"),
        "digest_valid": receipt.get("digest_valid"),
    },
    "recent_run_ids": run_ids,
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_RECEIPT_AND_LIST_RECENT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
