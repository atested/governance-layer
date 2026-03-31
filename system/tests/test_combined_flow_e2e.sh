#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_combined_flow_e2e"
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
os.environ["GOV_GOVERNED_FAMILY"] = "test_family"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "test_ctx"
os.environ["GOV_POLICY_VERSION"] = "test_v1"
os.environ["GOV_SIGNING_DEV_MODE"] = "1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from approval_store import load_approval_store_from_chain
from mcp import server
from transparency import compute_artifact_identity_prefixed
from verification import load_verification_state_from_chain


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


cert = server.certify_surface("test_family")
assert cert["from_state"] == "unverified"
assert cert["to_state"] == "verified"

transparent_target = tmp / "transparent.txt"
transparent_result = server.fs_write(str(transparent_target), "transparent-ok", overwrite=False)
assert transparent_result["policy_decision"] == "ALLOW"
assert transparent_result["decision_record"]["verification_state"] == "verified"

approved_artifact = tmp / "approved.opaque"
approved_artifact.write_bytes(b"approved-combined-flow")
approved_identity = compute_artifact_identity_prefixed(approved_artifact.read_bytes())
approval_event = server.approve_artifact(approved_identity, "test_operator")
assert approval_event["event_type"] == "opaque_artifact_approval"

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
assert approved_result["decision_record"]["resolution"] == "approved_lookup"
assert approved_result["decision_record"]["verification_state"] == "verified"

denied_artifact = tmp / "denied.opaque"
denied_artifact.write_bytes(b"denied-combined-flow")
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
assert denied_result["decision_record"]["resolution"] == "denied"
assert denied_result["decision_record"]["verification_state"] == "verified"

drift = server.report_drift("test_family")
assert drift["from_state"] == "verified"
assert drift["to_state"] == "drift_detected"

read_result = server.fs_read(str(transparent_target), max_bytes=4096, offset=0, as_text=True)
assert read_result["policy_decision"] == "ALLOW"
assert read_result["decision_record"]["verification_state"] == "drift_detected"

probe_apply = server.run_probe_and_apply("test_family", "capability_registry_probe")
assert probe_apply["probe_result"]["passed"] is True
assert probe_apply["target_state"] == "verified"
assert probe_apply["transition_event"]["from_state"] == "drift_detected"
assert probe_apply["transition_event"]["to_state"] == "verified"

chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
verify = subprocess.run(
    [sys.executable, str(root / "scripts" / "verify-chain.py"), str(chain_path)],
    capture_output=True,
    text=True,
    check=False,
)
if verify.returncode != 0:
    raise SystemExit(verify.stdout + verify.stderr)
assert "PASS: chain verified" in verify.stdout

rows = read_chain()
assert any(row.get("event_type") == "verification_state_transition" for row in rows)
assert any(row.get("event_type") == "opaque_artifact_approval" for row in rows)
assert sum(1 for row in rows if row.get("event_type") == "opaque_invocation_decision") == 2
assert sum(1 for row in rows if "event_type" not in row) == 2

reconstructed = load_verification_state_from_chain(str(chain_path))
assert reconstructed.get_state("test_family") == "verified"

approval_store = load_approval_store_from_chain(str(chain_path))
active = approval_store.lookup(approved_identity, "test_family", "test_ctx", "test_v1")
assert active is not None
assert active["approving_operator"] == "test_operator"

print("T10_COMBINED_FLOW_E2E=PASS")
print(f"CHAIN_PATH={chain_path}")
PY

bash system/tests/test_verification_runtime_wiring.sh
bash system/tests/test_mcp_capabilities_execute_core.sh

echo "T10_REGRESSION=PASS"
