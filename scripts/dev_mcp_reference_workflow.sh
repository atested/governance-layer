#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'USAGE'
usage: scripts/dev_mcp_reference_workflow.sh
Runs deterministic MCP governed FS reference workflow over stdio.
USAGE
}

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "FAIL: unknown arg: $1"
      usage
      exit 2
      ;;
  esac
fi

python3 - "$ROOT" <<'PY'
import json
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
run_id = "RID_MCP_REFERENCE_WORKFLOW"
work = root / "out" / "mcp_reference_workflow"
receipt_dir = root / "out" / "mcp_exec" / run_id
bundle_rel = f"out/mcp_reference_workflow/attestation/{run_id}"
bundle_dir = root / bundle_rel

private_pem = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
"""

shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(receipt_dir, ignore_errors=True)
work.mkdir(parents=True, exist_ok=True)
(work / "src.txt").write_text("reference-workflow\n", encoding="utf-8")


def rpc(method: str, params: dict) -> dict:
    req = {"id": method, "method": method, "params": params}
    proc = subprocess.run(
        ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
        input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"FAIL:{method}:RPC")
    return json.loads(proc.stdout.strip())["result"]

list_res = rpc("capabilities.list", {})
cap_names = [c.get("name") for c in list_res.get("capabilities", []) if isinstance(c, dict)]
if "FS_MOVE" not in cap_names:
    raise SystemExit("FAIL:capabilities.list")
print("MCP_LIST_OK")

desc = rpc("capabilities.describe", {"name": "FS_MOVE"})
if not desc.get("ok") or desc.get("name") != "FS_MOVE":
    raise SystemExit("FAIL:capabilities.describe")
print("MCP_DESCRIBE_OK")

action = {
    "name": "FS_COPY",
    "params": {
        "src_path": "out/mcp_reference_workflow/src.txt",
        "dst_path": "out/mcp_reference_workflow/dst.txt",
        "overwrite": True,
    },
}

norm = rpc("capabilities.normalize_action", {"action": action})
if not norm.get("ok"):
    raise SystemExit("FAIL:capabilities.normalize_action")
print("MCP_NORMALIZE_OK")

pre_default = rpc(
    "capabilities.admissibility_check",
    {"capabilities_version": "v0", "policy_context": "DEFAULT", "action": action},
)
if pre_default.get("admissible") is not True:
    raise SystemExit("FAIL:preflight_default")
print("MCP_PREFLIGHT_DEFAULT_OK")

pre_strict = rpc(
    "capabilities.admissibility_check",
    {"capabilities_version": "v0", "policy_context": "STRICT_OUT_ONLY", "action": action},
)
if pre_strict.get("admissible"):
    print("MCP_PREFLIGHT_STRICT_OUT_ONLY_OK")
else:
    print("MCP_PREFLIGHT_STRICT_OUT_ONLY_NO")

exec_res = rpc(
    "capabilities.execute",
    {
        "capabilities_version": "v0",
        "action": action,
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": run_id,
            "attested": True,
            "signing_key": private_pem,
            "emit_replay_artifact": True,
            "replay_policy_context": "DEFAULT",
            "attestation_out_dir": bundle_rel,
        },
    },
)
if exec_res.get("executed") is not True:
    raise SystemExit("FAIL:execute_attested")
if exec_res.get("replay_artifact", {}).get("present") is not True:
    raise SystemExit("FAIL:replay_artifact_missing")
print("MCP_EXEC_ATTESTED_OK")

vproc = subprocess.run(
    ["python3", str(root / "scripts/verify-attestation-bundle.py"), bundle_rel],
    text=True,
    capture_output=True,
    check=False,
)
if vproc.returncode != 0:
    raise SystemExit("FAIL:bundle_verify")
if not bundle_dir.is_dir():
    raise SystemExit("FAIL:bundle_dir")
print("BUNDLE_VERIFY_OK")

receipt = rpc("capabilities.receipt", {"run_id": run_id})
if receipt.get("digest_valid") is not True:
    raise SystemExit("FAIL:receipt")
print("RECEIPT_OK")

replay_default = rpc(
    "capabilities.replay_check",
    {"run_id": run_id, "policy_context": "DEFAULT", "emit_artifact": True},
)
if replay_default.get("admissible_now"):
    print("REPLAY_DEFAULT_OK")
else:
    raise SystemExit("FAIL:replay_default")

replay_strict = rpc(
    "capabilities.replay_check",
    {"run_id": run_id, "policy_context": "STRICT_OUT_ONLY", "emit_artifact": True},
)
if replay_strict.get("admissible_now"):
    print("REPLAY_STRICT_OUT_ONLY_OK")
else:
    print("REPLAY_STRICT_OUT_ONLY_NO")
PY
