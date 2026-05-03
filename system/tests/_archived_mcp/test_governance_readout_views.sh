#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_governance_readout_views"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

python3 - "$ROOT" "$TMP_ROOT/populated" <<'PY'
import json
import os
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

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

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

server.certify_surface("test_family")
transparent_target = tmp / "transparent.txt"
res = server.fs_write(str(transparent_target), "transparent-ok", overwrite=False)
assert res["policy_decision"] == "ALLOW"

approved_artifact = tmp / "approved.opaque"
approved_artifact.write_bytes(b"approved-readout")
approved_identity = compute_artifact_identity_prefixed(approved_artifact.read_bytes())
approval = server.approve_artifact(approved_identity, "test_operator")
assert approval["event_type"] == "opaque_artifact_approval"

approved_target = tmp / "approved.txt"
approved = server.governed_tool(
    "FS_WRITE",
    {
        "path": str(approved_target),
        "content": "approved",
        "overwrite": False,
        "opaque_artifact_path": str(approved_artifact),
        "opaque_executable": True,
    },
    {
        "goal": "approved opaque",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": str(approved_target)}],
    },
    write_action,
)
assert approved["decision_record"]["resolution"] == "approved_lookup"

denied_artifact = tmp / "denied.opaque"
denied_artifact.write_bytes(b"denied-readout")
denied_target = tmp / "denied.txt"
denied = server.governed_tool(
    "FS_WRITE",
    {
        "path": str(denied_target),
        "content": "denied",
        "overwrite": False,
        "opaque_artifact_path": str(denied_artifact),
        "opaque_executable": True,
    },
    {
        "goal": "denied opaque",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": str(denied_target)}],
    },
    write_action,
)
assert denied["decision_record"]["resolution"] == "denied"

drift = server.report_drift("test_family")
assert drift["to_state"] == "drift_detected"

status = server.governance_status()
assert status["chain_integrity"] == "ok"
assert status["verification_state"]["test_family"] == "drift_detected"
assert status["surfaces_in_drift"] == ["test_family"]
assert status["active_approvals_count"] == 1
assert status["opacity_posture"]["transparent_count"] == 1
assert status["opacity_posture"]["opaque_count"] == 2
assert status["runtime_outcome_summary"]["opaque_resolution_distribution"]["approved_lookup"] == 1
assert status["runtime_outcome_summary"]["opaque_resolution_distribution"]["denied"] == 1
assert status["reconstruction_status"]["verification_state"] == "ok"
assert status["reconstruction_status"]["approval_state"] == "ok"
assert len(status["approval_state"]["evidence_event_ids"]) == 1

approvals = server.governance_approvals()
assert approvals["total_count"] == 1
assert approvals["active_approvals"][0]["artifact_identity"] == approved_identity
assert approvals["active_approvals"][0]["approving_operator"] == "test_operator"
assert approvals["active_approvals"][0]["event_id"]

verification = server.governance_verification()
assert verification["total_tracked"] == 1
assert verification["surfaces"]["test_family"]["current_state"] == "drift_detected"
assert verification["surfaces"]["test_family"]["last_transition_event_id"] == drift["event_id"]
assert verification["surfaces_in_drift"] == ["test_family"]

filtered = server.governance_verification("missing_family")
assert filtered["total_tracked"] == 0
assert filtered["surfaces"] == {}
print("POPULATED_READOUT=PASS")
PY

python3 - "$ROOT" "$TMP_ROOT/empty" <<'PY'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

status = server.governance_status()
assert status["chain_event_count"] == 0
assert status["chain_integrity"] == "ok"
assert status["verification_state"] == {}
assert status["surfaces_in_drift"] == []
assert status["active_approvals_count"] == 0
assert status["opacity_posture"]["transparent_count"] == 0
assert status["runtime_outcome_summary"]["opaque_path_encounter_frequency"] == 0

approvals = server.governance_approvals()
assert approvals["total_count"] == 0
assert approvals["active_approvals"] == []

verification = server.governance_verification()
assert verification["total_tracked"] == 0
assert verification["surfaces"] == {}
print("EMPTY_READOUT=PASS")
PY

python3 - "$ROOT" "$TMP_ROOT/broken" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "broken_family"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

server.certify_surface("broken_family")
target = tmp / "file.txt"
result = server.fs_write(str(target), "ok", overwrite=False)
assert result["policy_decision"] == "ALLOW"

chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
rows = []
with open(chain_path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

rows[-1]["prev_record_hash"] = "sha256:broken"
with open(chain_path, "w", encoding="utf-8") as fh:
    for row in rows:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

status = server.governance_status()
assert isinstance(status["chain_integrity"], dict)
assert "broken_at" in status["chain_integrity"]
print("BROKEN_CHAIN_READOUT=PASS")
PY

bash system/tests/test_combined_flow_e2e.sh

echo "GOVERNANCE_READOUT_VIEWS=PASS"
