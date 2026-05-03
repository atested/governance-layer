#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_mcp_replay_check_emits_artifact"
rm -rf "$TMP_ROOT" out/mcp_exec
mkdir -p "$TMP_ROOT/fixtures"

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT/fixtures" out/mcp_exec
  mkdir -p "$TMP_ROOT/fixtures"
  printf 'replay-artifact\n' > "$TMP_ROOT/fixtures/src.txt"

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
                "src_path": "out/test_mcp_replay_check_emits_artifact/fixtures/src.txt",
                "dst_path": "out/test_mcp_replay_check_emits_artifact/fixtures/dst.txt",
                "overwrite": False,
            },
        },
        "mode": {"require_admissible": True, "dry_run": True, "run_id": "RID_REPLAY_ARTIFACT"},
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
if json.loads(proc.stdout.strip())["result"].get("admissible") is not True:
    raise SystemExit("FAIL:EXEC_NOT_ADMISSIBLE")

def replay(context):
    req = {
        "id": "REPLAY_" + context,
        "method": "capabilities.replay_check",
        "params": {
            "run_id": "RID_REPLAY_ARTIFACT",
            "policy_context": context,
            "emit_artifact": True,
        },
    }
    p = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise SystemExit("FAIL:REPLAY_RC")
    return json.loads(p.stdout.strip())["result"]

res_default = replay("DEFAULT")
res_strict = replay("STRICT_OUT_ONLY")

if res_default.get("admissible_now") is not True or res_default.get("reason_token") != "NONE":
    raise SystemExit("FAIL:DEFAULT_RESULT")
if res_strict.get("admissible_now") is not False or res_strict.get("reason_token") != "OUTSIDE_ALLOWED_ROOT":
    raise SystemExit("FAIL:STRICT_RESULT")

artifact = root / "out/mcp_exec/RID_REPLAY_ARTIFACT/replay_check.v0.json"
if not artifact.is_file():
    raise SystemExit("FAIL:ARTIFACT_MISSING")
artifact_obj = json.loads(artifact.read_text(encoding="utf-8"))
for key in [
    "replay_check_version",
    "run_id",
    "receipt_digest",
    "policy_context_used",
    "digest_valid",
    "admissible_now",
    "reason_token",
]:
    if key not in artifact_obj:
        raise SystemExit(f"FAIL:ARTIFACT_KEY:{key}")
if artifact_obj.get("replay_check_version") != "v0":
    raise SystemExit("FAIL:ARTIFACT_VERSION")
if artifact_obj.get("run_id") != "RID_REPLAY_ARTIFACT":
    raise SystemExit("FAIL:ARTIFACT_RUN_ID")
if artifact_obj.get("policy_context_used") != "STRICT_OUT_ONLY":
    raise SystemExit("FAIL:ARTIFACT_CONTEXT")

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
    "artifact": {
        "policy_context_used": artifact_obj.get("policy_context_used"),
        "reason_token": artifact_obj.get("reason_token"),
        "admissible_now": artifact_obj.get("admissible_now"),
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

echo "MCP_REPLAY_CHECK_EMITS_ARTIFACT=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
