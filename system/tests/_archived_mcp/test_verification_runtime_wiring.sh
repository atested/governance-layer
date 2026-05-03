#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_verification_runtime_wiring"
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
os.environ["GOV_GOVERNED_FAMILY"] = "vb_family"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "vb_ctx"
os.environ["GOV_POLICY_VERSION"] = "vb_policy"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server
from probe_harness import run_probe
from verification import (
    VerificationStateTracker,
    check_verification_state,
    evaluate_probe_result,
    load_verification_state_from_chain,
)


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


chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"

# 1. Probe execution -> concrete evidence-bearing ProbeResult.
probe = run_probe("capability_registry_probe", "vb_family")
assert probe.governed_family == "vb_family"
assert probe.property_tested == "capability_registry_probe"
assert isinstance(probe.evidence, dict)
assert probe.evidence["parseable"] is True
assert probe.evidence["file_hash"].startswith("sha256:")
assert probe.evidence["path"].endswith("capability-registry.json")

# 2. Probe evaluation semantics.
tracker = VerificationStateTracker()
assert evaluate_probe_result(probe, tracker) == "verified"
assert check_verification_state("vb_family", tracker) == "unverified"

# 3. Verification state transitions append correctly.
cert = server.certify_surface("vb_family")
assert cert["event_type"] == "verification_state_transition"
assert cert["from_state"] == "unverified"
assert cert["to_state"] == "verified"

drift = server.report_drift("vb_family")
assert drift["from_state"] == "verified"
assert drift["to_state"] == "drift_detected"

# 4. Probe-driven recertification through evaluate_probe_result().
probe_apply = server.run_probe_and_apply("vb_family", "capability_registry_probe")
assert probe_apply["probe_result"]["passed"] is True
assert probe_apply["target_state"] == "verified"
assert probe_apply["transition_event"]["event_type"] == "verification_state_transition"
assert probe_apply["transition_event"]["from_state"] == "drift_detected"
assert probe_apply["transition_event"]["to_state"] == "verified"

# 5. Explicit recertify on a second surface.
cert2 = server.certify_surface("vb_surface_b")
assert cert2["to_state"] == "verified"
drift2 = server.report_drift("vb_surface_b")
assert drift2["to_state"] == "drift_detected"
recert2 = server.recertify_surface("vb_surface_b")
assert recert2["from_state"] == "drift_detected"
assert recert2["to_state"] == "verified"

# 6. Reconstruction round-trip from chain.
reconstructed = load_verification_state_from_chain(str(chain_path))
assert reconstructed.get_state("vb_family") == "verified"
assert reconstructed.get_state("vb_surface_b") == "verified"
assert reconstructed.get_state("never_seen") == "unverified"

# 7. governed_tool annotation-only wiring.
target = tmp / "annotated.txt"
result = server.governed_tool(
    "FS_WRITE",
    {
        "path": str(target),
        "content": "annotation-check",
        "overwrite": False,
        "request_executable": False,
    },
    {
        "goal": "Verification annotation test",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [{"ref": "file:path", "value": str(target)}],
    },
    write_action,
)
assert result["policy_decision"] == "ALLOW"
assert result["decision_record"]["verification_state"] == "verified"
assert target.read_text(encoding="utf-8") == "annotation-check"

# 8. Chain remains valid after mixed verification and action flow.
verify = subprocess.run(
    [sys.executable, str(root / "scripts" / "verify-chain.py"), str(chain_path)],
    capture_output=True,
    text=True,
    check=False,
)
if verify.returncode != 0:
    raise SystemExit(verify.stdout + verify.stderr)
assert "PASS: chain verified" in verify.stdout

print("VB_RUNTIME_WIRING=PASS")
print(f"CHAIN_PATH={chain_path}")
PY

bash system/tests/test_verification_state_model.sh
bash system/tests/test_approval_revocation_and_opacity_metrics.sh

echo "VB_REGRESSION=PASS"
