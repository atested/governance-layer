#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_capabilities_execute_core"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/fixtures"
printf 'x\n' > "$TMP_ROOT/fixtures/src.txt"

OUT1="$TMP_ROOT/run1.json"
OUT2="$TMP_ROOT/run2.json"

run_once() {
  local out_file="$1"
  python3 - "$ROOT" "$out_file" <<'PY'
import json
import subprocess
import sys

root = sys.argv[1]
out_file = sys.argv[2]
cases = [
    {
        "id": "EXEC_OK_DRYRUN",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": "FS_MOVE", "params": {"src_path": "out/test_mcp_capabilities_execute_core/fixtures/src.txt", "dst_path": "out/test_mcp_capabilities_execute_core/fixtures/dst.txt"}},
            "mode": {"require_admissible": True, "dry_run": True},
        },
    },
    {
        "id": "EXEC_UNKNOWN",
        "method": "capabilities.execute",
        "params": {
            "capabilities_version": "v0",
            "action": {"name": "NOPE", "params": {"path": "out/test_mcp_capabilities_execute_core/fixtures/src.txt"}},
            "mode": {"require_admissible": True, "dry_run": False},
        },
    },
]

rows = []
for req in cases:
    proc = subprocess.run(
        ["python3", f"{root}/mcp/server.py", "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:EXECUTE_CORE_RC")
    payload = json.loads(proc.stdout.strip()).get("result", {})
    rows.append(payload)

rows.sort(key=lambda r: r.get("action_name", ""))
with open(out_file, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n")
PY
}

run_once "$OUT1"
run_once "$OUT2"

H1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
H2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

python3 - "$OUT1" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
move = next(r for r in rows if r.get("action_name") == "FS_MOVE")
unknown = next(r for r in rows if r.get("action_name") == "NOPE")
assert move["admissible"] is True
assert move["executed"] is False
assert move["reason_token"] == "NONE"
assert unknown["admissible"] is False
assert unknown["executed"] is False
assert unknown["reason_token"] == "CAPABILITY_UNKNOWN"
print("MCP_EXECUTE_CORE=PASS")
PY

echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
