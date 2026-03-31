#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_approval_revocation_and_opacity_metrics"
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
os.environ["GOV_GOVERNED_FAMILY"] = "w5_family"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "w5_ctx"
os.environ["GOV_POLICY_VERSION"] = "w5_policy"

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


def read_chain_rows():
    chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
    rows = []
    if chain_path.exists():
        with open(chain_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def opaque_write(artifact_path: Path, target: Path, content: str):
    return server.governed_tool(
        "FS_WRITE",
        {
            "path": str(target),
            "content": content,
            "overwrite": False,
            "opaque_artifact_path": str(artifact_path),
            "opaque_executable": True,
        },
        {
            "goal": "Opaque write test",
            "constraints": {"overwrite": False},
            "requested_action": "FS_WRITE",
            "inputs": [],
            "expected_outputs": [{"ref": "file:path", "value": str(target)}],
        },
        write_action,
    )


transparent_target = tmp / "transparent.txt"
transparent_result = server.fs_write(str(transparent_target), "transparent", overwrite=False)
assert transparent_result["policy_decision"] == "ALLOW"

artifact = tmp / "approved.opaque"
artifact.write_bytes(b"opaque-approval-test")
artifact_identity = compute_artifact_identity_prefixed(artifact.read_bytes())

approval_event = server.approve_artifact(artifact_identity, "operator@example")
assert approval_event["event_type"] == "opaque_artifact_approval"

active_after_approve = server.list_active_approvals()
assert len(active_after_approve["approvals"]) == 1
assert active_after_approve["approvals"][0]["artifact_identity"] == artifact_identity

approved_target = tmp / "approved.txt"
approved_result = opaque_write(artifact, approved_target, "approved-write")
assert approved_result["policy_decision"] == "ALLOW"
assert approved_result["decision_record"]["resolution"] == "approved_lookup"
assert approved_target.read_text(encoding="utf-8") == "approved-write"

revocation_event = server.revoke_artifact(artifact_identity, "operator@example")
assert revocation_event["event_type"] == "opaque_artifact_revocation"

active_after_revoke = server.list_active_approvals()
assert active_after_revoke["approvals"] == []

denied_target = tmp / "denied.txt"
denied_result = opaque_write(artifact, denied_target, "denied-write")
assert denied_result["policy_decision"] == "DENY"
assert denied_result["decision_record"]["resolution"] == "denied"
assert not denied_target.exists()

chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
verify = subprocess.run(
    [sys.executable, str(root / "scripts" / "verify-chain.py"), str(chain_path)],
    capture_output=True,
    text=True,
    check=False,
)
if verify.returncode != 0:
    raise SystemExit(verify.stdout + verify.stderr)

rows = read_chain_rows()
assert [row.get("event_type") for row in rows] == [
    None,
    "opaque_artifact_approval",
    "opaque_invocation_decision",
    "opaque_artifact_revocation",
    "opaque_invocation_decision",
]
assert rows[2]["resolution"] == "approved_lookup"
assert rows[4]["resolution"] == "denied"

json_once = subprocess.run(
    [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(chain_path), "--format", "json"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
json_twice = subprocess.run(
    [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(chain_path), "--format", "json"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
assert json_once == json_twice

metrics = json.loads(json_once)
assert metrics["transparent_vs_opaque_proportion"]["transparent_actions"] == 1
assert metrics["transparent_vs_opaque_proportion"]["opaque_encounters"] == 2
assert metrics["opaque_path_encounter_frequency"] == 2
assert metrics["resolution_distribution"] == {
    "approved_lookup": 1,
    "transparent_restatement": 0,
    "operator_intervention": 0,
    "denied": 1,
}

text_metrics = subprocess.run(
    [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(chain_path), "--format", "text"],
    capture_output=True,
    text=True,
    check=True,
).stdout
assert "transparent_actions=1" in text_metrics
assert "opaque_encounters=2" in text_metrics
assert "resolution_approved_lookup=1" in text_metrics
assert "resolution_denied=1" in text_metrics

empty_chain = tmp / "empty.jsonl"
empty_chain.write_text("", encoding="utf-8")
empty_metrics = json.loads(
    subprocess.run(
        [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(empty_chain), "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
)
assert empty_metrics["transparent_vs_opaque_proportion"]["total_governed_actions"] == 0
assert empty_metrics["opaque_path_encounter_frequency"] == 0

transparent_only_chain = tmp / "transparent_only.jsonl"
with open(transparent_only_chain, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(rows[0], sort_keys=True, separators=(",", ":")) + "\n")
transparent_only_metrics = json.loads(
    subprocess.run(
        [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(transparent_only_chain), "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
)
assert transparent_only_metrics["transparent_vs_opaque_proportion"]["transparent_actions"] == 1
assert transparent_only_metrics["transparent_vs_opaque_proportion"]["opaque_encounters"] == 0

opaque_only_chain = tmp / "opaque_only.jsonl"
with open(opaque_only_chain, "w", encoding="utf-8") as fh:
    for row in [rows[2], rows[4]]:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
opaque_only_metrics = json.loads(
    subprocess.run(
        [sys.executable, str(root / "scripts" / "opacity-metrics.py"), str(opaque_only_chain), "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
)
assert opaque_only_metrics["transparent_vs_opaque_proportion"]["transparent_actions"] == 0
assert opaque_only_metrics["transparent_vs_opaque_proportion"]["opaque_encounters"] == 2

print("W5_APPROVAL_AND_METRICS=PASS")
print(f"CHAIN_PATH={chain_path}")
PY

bash system/tests/test_transparency_opaque_path.sh
bash system/tests/test_governance_flow_integration_e2e.sh

echo "W5_REGRESSION=PASS"
