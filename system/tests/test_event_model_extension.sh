#!/usr/bin/env bash
set -euo pipefail

# Test: Event Model Extension (W1)
#
# Validates:
#   1. Compound metadata acceptance and validation
#   2. dependency_type validation (data, state, control)
#   3. Non-action event types (verification_state_transition,
#      opaque_artifact_approval, opaque_artifact_revocation,
#      opaque_invocation_decision)
#   4. Chain integrity across mixed action and non-action events
#   5. Replay tooling handles non-action events as chain-valid skips
#   6. Backward compatibility — existing records remain valid

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_event_model_extension"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Event Model Extension Tests ==="

# ---------------------------------------------------------------------------
# 1. Unit tests via embedded Python
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: compound metadata and non-action event validation ---"

python3 - "$ROOT" <<'PYEOF'
import json
import sys
import os

root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))

from event_model import (
    validate_compound_metadata,
    validate_non_action_event,
    verify_non_action_event_hash,
    build_non_action_event,
    is_non_action_event,
    NON_ACTION_EVENT_TYPES,
    ALLOWED_DEPENDENCY_TYPES,
)

PASS = 0
FAIL = 0

def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label} — {detail}")

# --- Compound metadata ---

# Valid compound metadata
ok, err = validate_compound_metadata({
    "compound_action_id": "compound-001",
    "depends_on": [
        {"step_id": "step-a", "dependency_type": "data"},
    ],
})
check("valid compound metadata (single dep)", ok, err)

# Valid with multiple deps
ok, err = validate_compound_metadata({
    "compound_action_id": "compound-002",
    "depends_on": [
        {"step_id": "step-a", "dependency_type": "data"},
        {"step_id": "step-b", "dependency_type": "state"},
        {"step_id": "step-a", "dependency_type": "control"},
    ],
})
check("valid compound metadata (multi dep)", ok, err)

# Missing compound_action_id
ok, err = validate_compound_metadata({
    "depends_on": [{"step_id": "s", "dependency_type": "data"}],
})
check("reject missing compound_action_id", not ok, err)

# Empty depends_on
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [],
})
check("reject empty depends_on", not ok, err)

# Invalid dependency_type
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [{"step_id": "s", "dependency_type": "unknown"}],
})
check("reject invalid dependency_type", not ok, err)

# Duplicate dependency
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [
        {"step_id": "s", "dependency_type": "data"},
        {"step_id": "s", "dependency_type": "data"},
    ],
})
check("reject duplicate dependency", not ok, err)

# Missing step_id
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [{"dependency_type": "data"}],
})
check("reject missing step_id", not ok, err)

# Unrecognized keys in dep
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [{"step_id": "s", "dependency_type": "data", "extra": 1}],
})
check("reject extra keys in depends_on entry", not ok, err)

# Unrecognized keys at top level
ok, err = validate_compound_metadata({
    "compound_action_id": "c-1",
    "depends_on": [{"step_id": "s", "dependency_type": "data"}],
    "plan_id": "p-1",
})
check("reject extra top-level keys", not ok, err)

# All three dependency types accepted
for dt in sorted(ALLOWED_DEPENDENCY_TYPES):
    ok, err = validate_compound_metadata({
        "compound_action_id": "c-1",
        "depends_on": [{"step_id": "s", "dependency_type": dt}],
    })
    check(f"accept dependency_type={dt}", ok, err)

# --- Non-action event construction and validation ---

# verification_state_transition
evt = build_non_action_event("verification_state_transition", {
    "governed_family": "mcp_tools_v1",
    "from_state": "unverified",
    "to_state": "verified",
})
check("build verification_state_transition", evt.get("event_type") == "verification_state_transition")
check("is_non_action_event", is_non_action_event(evt))
ok, err = validate_non_action_event(evt)
check("validate verification_state_transition", ok, err)
ok, err = verify_non_action_event_hash(evt)
check("hash verification_state_transition", ok, err)

# Same from_state and to_state rejected
evt_bad = build_non_action_event("verification_state_transition", {
    "governed_family": "f",
    "from_state": "verified",
    "to_state": "verified",
})
ok, err = validate_non_action_event(evt_bad)
check("reject same from_state and to_state", not ok, err)

# Invalid state value
evt_bad2 = build_non_action_event("verification_state_transition", {
    "governed_family": "f",
    "from_state": "verified",
    "to_state": "unknown_state",
})
ok, err = validate_non_action_event(evt_bad2)
check("reject invalid state value", not ok, err)

# opaque_artifact_approval
evt = build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "approving_operator": "operator@example.com",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "production",
    "policy_version": "baseline_v1.1",
})
ok, err = validate_non_action_event(evt)
check("validate opaque_artifact_approval", ok, err)
ok, err = verify_non_action_event_hash(evt)
check("hash opaque_artifact_approval", ok, err)

# opaque_artifact_revocation
evt = build_non_action_event("opaque_artifact_revocation", {
    "artifact_identity": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "revoking_operator": "operator@example.com",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "production",
    "policy_version": "baseline_v1.1",
})
ok, err = validate_non_action_event(evt)
check("validate opaque_artifact_revocation", ok, err)
ok, err = verify_non_action_event_hash(evt)
check("hash opaque_artifact_revocation", ok, err)

# opaque_invocation_decision
for resolution in ["approved_lookup", "transparent_restatement", "operator_intervention", "denied"]:
    evt = build_non_action_event("opaque_invocation_decision", {
        "artifact_identity": "sha256:abc123",
        "governed_family": "mcp_tools_v1",
        "resolution": resolution,
    })
    ok, err = validate_non_action_event(evt)
    check(f"validate opaque_invocation_decision resolution={resolution}", ok, err)

# Invalid resolution
evt = build_non_action_event("opaque_invocation_decision", {
    "artifact_identity": "sha256:abc123",
    "governed_family": "mcp_tools_v1",
    "resolution": "auto_approved",
})
ok, err = validate_non_action_event(evt)
check("reject invalid resolution", not ok, err)

# Missing required field
evt = build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": "sha256:abc",
    # missing approving_operator, governed_family, etc.
})
ok, err = validate_non_action_event(evt)
check("reject approval missing required fields", not ok, err)

# Non-action event with compound metadata
evt = build_non_action_event(
    "verification_state_transition",
    {
        "governed_family": "f1",
        "from_state": "unverified",
        "to_state": "verified",
    },
    compound_metadata={
        "compound_action_id": "compound-setup",
        "depends_on": [{"step_id": "provision-step", "dependency_type": "state"}],
    },
)
ok, err = validate_non_action_event(evt)
check("non-action event with compound metadata", ok, err)

# Tampered hash detection
evt = build_non_action_event("verification_state_transition", {
    "governed_family": "f1",
    "from_state": "verified",
    "to_state": "drift_detected",
})
evt["governed_family"] = "tampered"
ok, err = verify_non_action_event_hash(evt)
check("detect tampered non-action event", not ok, err)

# Action records are NOT non-action events
action_rec = {"tool": "FS_WRITE", "policy_decision": "ALLOW"}
check("action record is not non_action_event", not is_non_action_event(action_rec))

print(f"\nUnit results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
  pass "unit tests"
else
  fail "unit tests"
fi

# ---------------------------------------------------------------------------
# 2. verify-record integration: action records with compound metadata
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: verify-record with compound metadata ---"

# Build an action record that has compound_metadata and verify it.
# We use verify_record_dict with check_cap_registry_hash=False since the
# fixture records were generated with a different registry version.

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os
import hashlib

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from event_model import validate_compound_metadata
import importlib.util

# Load a known-good record and add compound_metadata.
record_path = os.path.join(root, "LOGS", "t-fs-001.record.json")
with open(record_path) as f:
    rec = json.load(f)

# Add compound metadata.
rec["compound_metadata"] = {
    "compound_action_id": "compound-test-001",
    "depends_on": [
        {"step_id": "step-init", "dependency_type": "state"},
        {"step_id": "step-read", "dependency_type": "data"},
    ],
}

# Recompute record_hash (signing preimage convention: record_hash=None, signature=None).
rec_copy = dict(rec)
rec_copy["record_hash"] = None
rec_copy["signature"] = None
canonical = json.dumps(rec_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
rec["record_hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

out_path = os.path.join(tmp, "action_with_compound.json")
with open(out_path, "w") as f:
    json.dump(rec, f, indent=2)

# Verify using the module directly (skip cap_registry_hash check).
spec = importlib.util.spec_from_file_location(
    "verify_record_impl", os.path.join(root, "scripts", "verify-record.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rc, lines = mod.verify_record_dict(rec, check_cap_registry_hash=False)
for line in lines:
    print(line)
if rc != 0:
    print("COMPOUND_META_TEST=FAIL")
    sys.exit(1)
print("COMPOUND_META_TEST=PASS")
PYEOF

if [ $? -eq 0 ]; then
  pass "verify-record accepts action with compound_metadata"
else
  fail "verify-record rejects action with compound_metadata"
fi

# Verify that invalid compound_metadata is rejected.
python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os
import hashlib
import importlib.util

root = sys.argv[1]
tmp = sys.argv[2]

record_path = os.path.join(root, "LOGS", "t-fs-001.record.json")
with open(record_path) as f:
    rec = json.load(f)

rec["compound_metadata"] = {
    "compound_action_id": "c-1",
    "depends_on": [{"step_id": "s", "dependency_type": "invalid_type"}],
}
rec_copy = dict(rec)
rec_copy["record_hash"] = None
rec_copy["signature"] = None
canonical = json.dumps(rec_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
rec["record_hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

spec = importlib.util.spec_from_file_location(
    "verify_record_impl", os.path.join(root, "scripts", "verify-record.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rc, lines = mod.verify_record_dict(rec, check_cap_registry_hash=False)
for line in lines:
    print(line)
if rc != 0:
    print("BAD_COMPOUND_TEST=PASS")  # Expected to fail.
else:
    print("BAD_COMPOUND_TEST=FAIL")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
  pass "verify-record rejects action with invalid compound_metadata"
else
  fail "verify-record should reject invalid compound_metadata"
fi

# ---------------------------------------------------------------------------
# 3. verify-record integration: non-action events
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: verify-record with non-action events ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from event_model import build_non_action_event

events = {
    "vst": build_non_action_event("verification_state_transition", {
        "governed_family": "mcp_tools_v1",
        "from_state": "unverified",
        "to_state": "verified",
    }),
    "approval": build_non_action_event("opaque_artifact_approval", {
        "artifact_identity": "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "approving_operator": "admin@gov.example",
        "governed_family": "mcp_tools_v1",
        "deployment_context": "staging",
        "policy_version": "v1.1",
    }),
    "revocation": build_non_action_event("opaque_artifact_revocation", {
        "artifact_identity": "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "revoking_operator": "admin@gov.example",
        "governed_family": "mcp_tools_v1",
        "deployment_context": "staging",
        "policy_version": "v1.1",
    }),
    "invocation": build_non_action_event("opaque_invocation_decision", {
        "artifact_identity": "sha256:deadbeef",
        "governed_family": "mcp_tools_v1",
        "resolution": "approved_lookup",
    }),
}

for name, evt in events.items():
    path = os.path.join(tmp, f"event_{name}.json")
    with open(path, "w") as f:
        json.dump(evt, f, indent=2)
    print(f"wrote {path}")
PYEOF

for EVT_NAME in vst approval revocation invocation; do
  VERIFY_OUT=$(python3 "$ROOT/scripts/verify-record.py" "$TMP_BASE/event_${EVT_NAME}.json" 2>&1) || true
  if echo "$VERIFY_OUT" | grep -q "PASS:"; then
    pass "verify-record accepts non-action event: $EVT_NAME"
  else
    fail "verify-record rejects non-action event $EVT_NAME: $VERIFY_OUT"
  fi
done

# ---------------------------------------------------------------------------
# 4. Chain integrity: mixed action and non-action events
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: chain integrity across mixed event types ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import subprocess
import sys
import os
import hashlib
import tempfile

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from event_model import build_non_action_event

# Build a chain: action record → non-action event → non-action event.
# Generate a fresh action record using policy-eval so cap_registry_hash matches.
intent = {
    "tool": "FS_WRITE",
    "args": {
        "path": os.path.join(root, "out", "test_chain_dummy.txt"),
        "content": "test",
        "request_executable": False,
    },
    "intent": {
        "goal": "Write test file for chain test",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "expected_outputs": [
            {"ref": "file:path", "value": os.path.join(root, "out", "test_chain_dummy.txt")}
        ],
    },
}

intent_path = os.path.join(tmp, "chain_intent.json")
with open(intent_path, "w") as f:
    json.dump(intent, f)

os.environ["GOV_CANONICAL_REPO_PATH"] = root
os.environ["GOV_RUNTIME_PATH"] = os.path.join(tmp, "runtime")
os.makedirs(os.environ["GOV_RUNTIME_PATH"], exist_ok=True)

result = subprocess.run(
    [sys.executable, os.path.join(root, "scripts", "policy-eval.py"), intent_path],
    capture_output=True, text=True,
)
if result.returncode != 0:
    print(f"policy-eval failed: {result.stderr}", file=sys.stderr)
    sys.exit(2)

action_rec = json.loads(result.stdout)

# Ensure prev_record_hash is null for chain head, recompute hash.
action_rec["prev_record_hash"] = None
rec_copy = dict(action_rec)
rec_copy["record_hash"] = None
rec_copy["signature"] = None
canonical = json.dumps(rec_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
action_rec["record_hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# Non-action event linking to the action record.
vst_event = build_non_action_event(
    "verification_state_transition",
    {
        "governed_family": "mcp_tools_v1",
        "from_state": "unverified",
        "to_state": "verified",
    },
    prev_record_hash=action_rec["record_hash"],
)

# Another non-action event.
approval_event = build_non_action_event(
    "opaque_artifact_approval",
    {
        "artifact_identity": "sha256:abc123",
        "approving_operator": "admin",
        "governed_family": "mcp_tools_v1",
        "deployment_context": "prod",
        "policy_version": "v1",
    },
    prev_record_hash=vst_event["record_hash"],
)

# Write as JSONL chain.
chain_path = os.path.join(tmp, "mixed_chain.jsonl")
with open(chain_path, "w") as f:
    for rec in [action_rec, vst_event, approval_event]:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")

print(f"wrote {chain_path}")
PYEOF

CHAIN_OUT=$(python3 "$ROOT/scripts/verify-chain.py" "$TMP_BASE/mixed_chain.jsonl" 2>&1) || true
if echo "$CHAIN_OUT" | grep -q "PASS: chain verified"; then
  pass "mixed chain (action + non-action) verifies"
  # Check that it reports the right counts.
  if echo "$CHAIN_OUT" | grep -q "1 action, 2 non-action"; then
    pass "chain reports correct action/non-action counts"
  else
    fail "chain count mismatch: $CHAIN_OUT"
  fi
else
  fail "mixed chain verification failed: $CHAIN_OUT"
fi

# ---------------------------------------------------------------------------
# 5. Replay: non-action events are skipped gracefully
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: replay skips non-action events ---"

REPLAY_OUT=$(python3 "$ROOT/scripts/replay-record.py" "$TMP_BASE/event_vst.json" 2>&1) || true
if echo "$REPLAY_OUT" | grep -q "SKIP:"; then
  pass "replay skips non-action event"
else
  fail "replay did not skip non-action event: $REPLAY_OUT"
fi

# ---------------------------------------------------------------------------
# 6. Backward compatibility: existing records remain valid
# ---------------------------------------------------------------------------
echo ""
echo "--- Backward compatibility ---"

# Verify existing records using the module API with cap_registry_hash check
# disabled, since fixture records were generated with older registry versions.
python3 - "$ROOT" <<'PYEOF'
import json
import sys
import os
import importlib.util
import glob

root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))

spec = importlib.util.spec_from_file_location(
    "verify_record_impl", os.path.join(root, "scripts", "verify-record.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

passed = 0
failed = 0

for record_path in sorted(glob.glob(os.path.join(root, "LOGS", "t-fs-00*.record.json"))):
    with open(record_path) as f:
        rec = json.load(f)
    rc, lines = mod.verify_record_dict(rec, check_cap_registry_hash=False)
    basename = os.path.basename(record_path)
    if rc == 0:
        passed += 1
        print(f"  PASS: existing record {basename} still valid")
    else:
        failed += 1
        print(f"  FAIL: existing record {basename} broke: {lines}")

print(f"\nBackward compat records: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
  pass "backward compatibility: existing records"
else
  fail "backward compatibility: existing records"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
