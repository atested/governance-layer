#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_receipt_store_index"
rm -rf "$TMP_ROOT" out/mcp_exec
mkdir -p "$TMP_ROOT/fixtures"
printf 'one\n' > "$TMP_ROOT/fixtures/a.txt"
printf 'two\n' > "$TMP_ROOT/fixtures/b.txt"

run_once() {
  local out_file="$1"
  rm -rf out/mcp_exec
  rm -rf "$TMP_ROOT/fixtures"
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'one\n' > "$TMP_ROOT/fixtures/a.txt"
  printf 'two\n' > "$TMP_ROOT/fixtures/b.txt"

  python3 - "$ROOT" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
requests = [
    {
        "id": "IDX2",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": "FS_MOVE", "params": {"src_path": "out/test_mcp_receipt_store_index/fixtures/a.txt", "dst_path": "out/test_mcp_receipt_store_index/fixtures/a_moved.txt"}},
            "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_B"},
        },
    },
    {
        "id": "IDX1",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": "FS_COPY", "params": {"src_path": "out/test_mcp_receipt_store_index/fixtures/b.txt", "dst_path": "out/test_mcp_receipt_store_index/fixtures/b_copy.txt"}},
            "mode": {"require_admissible": True, "dry_run": False, "run_id": "RID_A"},
        },
    },
]
for req in requests:
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:EXEC_RC")
PY

  python3 - "$ROOT" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
index_path = root / "out/mcp_exec/index.v1.json"
if not index_path.exists():
    raise SystemExit("FAIL:INDEX_MISSING")
obj = json.loads(index_path.read_text(encoding="utf-8"))
rows = obj.get("receipts", [])
if len(rows) != 2:
    raise SystemExit("FAIL:INDEX_COUNT")
run_ids = [r["run_id"] for r in rows]
if run_ids != sorted(run_ids):
    raise SystemExit("FAIL:INDEX_NOT_SORTED")
for row in rows:
    rid = row["run_id"]
    digest = row["digest"]
    rec = root / "out/mcp_exec" / rid / "action_record.json"
    digf = root / "out/mcp_exec" / rid / "action_record.sha256"
    if not rec.exists() or not digf.exists():
        raise SystemExit("FAIL:RECORD_OR_DIGEST_MISSING")
    body = rec.read_text(encoding="utf-8")
    expected = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    actual = digf.read_text(encoding="utf-8").strip()
    if digest != expected or actual != expected:
        raise SystemExit("FAIL:DIGEST_MISMATCH")
out_file.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_ROOT/run1.json"
RUN2="$TMP_ROOT/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_RECEIPT_STORE_INDEX=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
