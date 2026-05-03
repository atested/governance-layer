#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_governance_flow_integration_e2e"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

python3 - "$ROOT" "$TMP_ROOT" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])

runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)
os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "w4_family"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "w4_ctx"
os.environ["GOV_POLICY_VERSION"] = "w4_policy"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from event_model import build_non_action_event
from mcp import server
from transparency import compute_artifact_identity_prefixed


def write_action(_rec, args):
    target = Path(args["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args["content"], encoding="utf-8")
    return {
        "write_result": {
            "bytes_written": len(args["content"].encode("utf-8")),
            "canonical_path": str(target.resolve()),
        }
    }


def read_chain():
    chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
    rows = []
    if chain_path.exists():
        with open(chain_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


transparent_target = tmp / "transparent.txt"
transparent_result = server.fs_write(str(transparent_target), "transparent-ok", overwrite=False)
assert transparent_result["policy_decision"] == "ALLOW"
assert transparent_target.read_text(encoding="utf-8") == "transparent-ok"

chain = read_chain()
assert len(chain) == 1, chain
transparent_record = chain[0]
assert transparent_record.get("policy_decision") == "ALLOW"
assert transparent_record.get("event_type") is None

approved_artifact = tmp / "approved.opaque"
approved_artifact.write_bytes(b"approved-opaque-artifact")
approved_identity = compute_artifact_identity_prefixed(approved_artifact.read_bytes())

approval_event = build_non_action_event(
    "opaque_artifact_approval",
    {
        "artifact_identity": approved_identity,
        "approving_operator": "tester",
        "governed_family": "w4_family",
        "deployment_context": "w4_ctx",
        "policy_version": "w4_policy",
    },
    prev_record_hash=transparent_record["record_hash"],
)
server._append_non_action_event(approval_event)
server._verify_chain()

denied_artifact = tmp / "denied.opaque"
denied_artifact.write_bytes(b"denied-opaque-artifact")
denied_target = tmp / "denied.txt"
denied_result = server.governed_tool(
    "FS_WRITE",
    {
        "path": str(denied_target),
        "content": "denied-write",
        "overwrite": False,
        "opaque_artifact_path": str(denied_artifact),
        "opaque_executable": True,
    },
    {
        "goal": "Denied opaque write test",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": str(denied_target)}],
    },
    write_action,
)
assert denied_result["policy_decision"] == "DENY"
assert denied_result["decision_record"]["event_type"] == "opaque_invocation_decision"
assert denied_result["decision_record"]["resolution"] == "denied"
assert not denied_target.exists()

approved_target = tmp / "approved.txt"
approved_result = server.governed_tool(
    "FS_WRITE",
    {
        "path": str(approved_target),
        "content": "approved-write",
        "overwrite": False,
        "opaque_artifact_path": str(approved_artifact),
        "opaque_executable": True,
    },
    {
        "goal": "Approved opaque write test",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": str(approved_target)}],
    },
    write_action,
)
assert approved_result["policy_decision"] == "ALLOW"
assert approved_result["decision_record"]["event_type"] == "opaque_invocation_decision"
assert approved_result["decision_record"]["resolution"] == "approved_lookup"
assert approved_target.read_text(encoding="utf-8") == "approved-write"

chain = read_chain()
assert [row.get("event_type") for row in chain] == [
    None,
    "opaque_artifact_approval",
    "opaque_invocation_decision",
    "opaque_invocation_decision",
]
assert chain[2]["resolution"] == "denied"
assert chain[3]["resolution"] == "approved_lookup"

verify = subprocess.run(
    [sys.executable, str(root / "scripts" / "verify-chain.py"), str(runtime_dir / "LOGS" / "decision-chain.jsonl")],
    capture_output=True,
    text=True,
    check=False,
)
if verify.returncode != 0:
    raise SystemExit(verify.stdout + verify.stderr)
assert "PASS: chain verified" in verify.stdout

print("W4_GOVERNANCE_FLOW_E2E=PASS")
print(f"CHAIN_PATH={runtime_dir / 'LOGS' / 'decision-chain.jsonl'}")
PY
