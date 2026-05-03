#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_fs_copy"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures/src_dir/nested"
printf 'alpha\n' > "$TMP_ROOT/fixtures/src_dir/file.txt"
printf 'beta\n' > "$TMP_ROOT/fixtures/src_dir/nested/inner.txt"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures/dst_dir"
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

req = {
    "id": "COPY_ONLY",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_capabilities_execute_fs_copy/fixtures/src_dir",
                "dst_path": "out/test_mcp_capabilities_execute_fs_copy/fixtures/dst_dir",
                "overwrite": False,
            },
        },
        "mode": {"require_admissible": True, "dry_run": False, "run_id": "EXEC_COPY_ONLY_FIXED"},
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
    raise SystemExit("FAIL:COPY_RC")
payload = json.loads(proc.stdout.strip())["result"]
if payload.get("executed") is not True:
    raise SystemExit("FAIL:COPY_NOT_EXECUTED")
if payload.get("reason_token") != "NONE":
    raise SystemExit("FAIL:COPY_BAD_REASON")
digest = payload.get("action_record_digest")
if not isinstance(digest, str) or not digest.startswith("sha256:"):
    raise SystemExit("FAIL:COPY_NO_DIGEST")

dst = root / "out/test_mcp_capabilities_execute_fs_copy/fixtures/dst_dir"
if not (dst / "file.txt").exists():
    raise SystemExit("FAIL:COPY_FILE_MISSING")
if not (dst / "nested/inner.txt").exists():
    raise SystemExit("FAIL:COPY_INNER_MISSING")

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

echo "MCP_EXECUTE_FS_COPY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
