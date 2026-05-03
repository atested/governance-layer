#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_replay_check_policy_context_drift"
rm -rf "$TMP_ROOT" out/mcp_exec
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures" out/mcp_exec
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'replay-drift\n' > "$TMP_ROOT/fixtures/src.txt"

  python3 - "$ROOT" "$out_file" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])

exec_req = {
    "id": "EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_mcp_replay_check_policy_context_drift/fixtures/src.txt",
                "dst_path": "out/test_mcp_replay_check_policy_context_drift/fixtures/dst.txt",
                "overwrite": False,
            },
        },
        "mode": {"require_admissible": True, "dry_run": True, "run_id": "RID_POLICY_DRIFT"},
    },
}
exec_proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(exec_req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if exec_proc.returncode != 0:
    raise SystemExit("FAIL:EXEC_RC")
exec_payload = json.loads(exec_proc.stdout.strip())["result"]
if exec_payload.get("admissible") is not True:
    raise SystemExit("FAIL:EXEC_NOT_ADMISSIBLE")

def call_replay(context):
    req = {
        "id": "REPLAY_" + context,
        "method": "capabilities.replay_check",
        "params": {"run_id": "RID_POLICY_DRIFT", "policy_context": context},
    }
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("FAIL:REPLAY_RC")
    return json.loads(proc.stdout.strip())["result"]

res_default = call_replay("DEFAULT")
res_strict = call_replay("STRICT_OUT_ONLY")

if res_default.get("admissible_now") is not True:
    raise SystemExit("FAIL:DEFAULT_NOT_ADMISSIBLE")
if res_default.get("reason_token") != "NONE":
    raise SystemExit("FAIL:DEFAULT_REASON")
if res_default.get("policy_context_used") != "DEFAULT":
    raise SystemExit("FAIL:DEFAULT_CONTEXT")

if res_strict.get("admissible_now") is not False:
    raise SystemExit("FAIL:STRICT_NOT_BLOCKED")
if res_strict.get("reason_token") != "OUTSIDE_ALLOWED_ROOT":
    raise SystemExit("FAIL:STRICT_REASON")
if res_strict.get("policy_context_used") != "STRICT_OUT_ONLY":
    raise SystemExit("FAIL:STRICT_CONTEXT")

out = {
    "default": {
        "admissible_now": res_default.get("admissible_now"),
        "reason_token": res_default.get("reason_token"),
        "policy_context_used": res_default.get("policy_context_used"),
    },
    "strict": {
        "admissible_now": res_strict.get("admissible_now"),
        "reason_token": res_strict.get("reason_token"),
        "policy_context_used": res_strict.get("policy_context_used"),
    },
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

echo "MCP_REPLAY_CHECK_POLICY_CONTEXT_DRIFT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
