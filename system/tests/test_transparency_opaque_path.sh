#!/usr/bin/env bash
set -euo pipefail

# Test: Transparency Classification and Opaque Path Handling (W3)
#
# Validates:
#   1. Transparency classification (transparent vs opaque)
#   2. Transparent fast path — no added friction
#   3. Artifact identity computation (SHA-256 lowercase hex)
#   4. Approval store — conjunctive scope matching
#   5. Opaque slow path — full flow (identity → lookup → restatement → friction)
#   6. Approved opaque artifact path
#   7. Unapproved opaque artifact — restatement stub returns not-possible
#   8. Friction path — denied resolution
#   9. No path/origin-based exceptions (unverified opaque executable rule)
#  10. Chain integrity for opaque_invocation_decision events
#  11. Existing transparent-path behavior unchanged

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_transparency_opaque_path"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Transparency Classification and Opaque Path Tests ==="

# ---------------------------------------------------------------------------
# 1. Unit tests via embedded Python
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: transparency classification, identity, approval, opaque path ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os
import hashlib

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from transparency import (
    classify_transparency,
    classify_action_transparency,
    compute_artifact_identity,
    compute_artifact_identity_prefixed,
    attempt_transparent_restatement,
    handle_opaque_action,
)
from approval_store import (
    ApprovalStore,
    load_approval_store_from_events,
)
from event_model import (
    build_non_action_event,
    validate_non_action_event,
    verify_non_action_event_hash,
)

# Load registry.
with open(os.path.join(root, "capabilities", "capability-registry.json")) as f:
    registry = json.load(f)

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

# --- Transparency classification ---

check("FS_WRITE is transparent",
      classify_transparency("FS_WRITE", "FS_WRITE", registry) == "transparent")
check("FS_READ is transparent",
      classify_transparency("FS_READ", "FS_READ", registry) == "transparent")
check("FS_LIST is transparent",
      classify_transparency("FS_LIST", "FS_LIST", registry) == "transparent")
check("FS_MOVE is transparent",
      classify_transparency("FS_MOVE", "FS_MOVE", registry) == "transparent")
check("FS_DELETE is transparent",
      classify_transparency("FS_DELETE", "FS_DELETE", registry) == "transparent")
check("unknown tool is opaque",
      classify_transparency("UNKNOWN_TOOL", "UNKNOWN_TOOL", registry) == "opaque")
check("empty tool is opaque",
      classify_transparency("", "", registry) == "opaque")

# classify_action_transparency
transparent_req = {"tool": "FS_WRITE", "args": {"path": "/tmp/x", "content": "y"}}
check("action without opaque marker is transparent",
      classify_action_transparency(transparent_req, registry) == "transparent")

opaque_req = {"tool": "FS_WRITE", "args": {"opaque_artifact_path": "/tmp/script.sh"}}
check("action with opaque_artifact_path is opaque",
      classify_action_transparency(opaque_req, registry) == "opaque")

opaque_req2 = {"tool": "FS_WRITE", "args": {"opaque_executable": True}}
check("action with opaque_executable is opaque",
      classify_action_transparency(opaque_req2, registry) == "opaque")

unknown_req = {"tool": "RUN_SCRIPT", "args": {}}
check("unregistered tool action is opaque",
      classify_action_transparency(unknown_req, registry) == "opaque")

# --- Artifact identity (§9.1) ---

content = b"#!/bin/bash\necho hello\n"
expected_hash = hashlib.sha256(content).hexdigest()
check("artifact identity matches SHA-256",
      compute_artifact_identity(content) == expected_hash)
check("artifact identity is lowercase hex",
      compute_artifact_identity(content) == compute_artifact_identity(content).lower())
check("prefixed identity has sha256: prefix",
      compute_artifact_identity_prefixed(content) == "sha256:" + expected_hash)

# Empty content has valid identity.
check("empty content has valid identity",
      compute_artifact_identity(b"") == hashlib.sha256(b"").hexdigest())

# Different content → different identity (§9.1: brittle to benign changes).
content2 = b"#!/bin/bash\necho hello\n\n"
check("different content → different identity",
      compute_artifact_identity(content) != compute_artifact_identity(content2))

# --- Transparent restatement stub (§8.4) ---

result = attempt_transparent_restatement({}, "sha256:abc", "fam1")
check("restatement returns not-possible at baseline", result["possible"] is False)
check("restatement has reason", isinstance(result["reason"], str) and len(result["reason"]) > 0)

# --- Approval store (§9.4, §9.5, §9.7) ---

store = ApprovalStore()

# Empty store → no approvals.
check("empty store returns None",
      store.lookup("sha256:abc", "fam", "prod", "v1") is None)

# Add an approval.
approval_event = build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": "sha256:abc123",
    "approving_operator": "admin@gov",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "production",
    "policy_version": "v1.1",
})
store.ingest_approval(approval_event)

# Exact scope match → found.
found = store.lookup("sha256:abc123", "mcp_tools_v1", "production", "v1.1")
check("exact scope match finds approval",
      found is not None and found["artifact_identity"] == "sha256:abc123")
check("approval has correct operator",
      found is not None and found["approving_operator"] == "admin@gov")

# Scope mismatch on any field → not found (conjunctive).
check("wrong artifact_identity → None",
      store.lookup("sha256:different", "mcp_tools_v1", "production", "v1.1") is None)
check("wrong governed_family → None",
      store.lookup("sha256:abc123", "different_family", "production", "v1.1") is None)
check("wrong deployment_context → None",
      store.lookup("sha256:abc123", "mcp_tools_v1", "staging", "v1.1") is None)
check("wrong policy_version → None",
      store.lookup("sha256:abc123", "mcp_tools_v1", "production", "v2.0") is None)

# Revocation removes approval.
revocation_event = build_non_action_event("opaque_artifact_revocation", {
    "artifact_identity": "sha256:abc123",
    "revoking_operator": "admin@gov",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "production",
    "policy_version": "v1.1",
})
store.ingest_revocation(revocation_event)
check("revocation removes approval",
      store.lookup("sha256:abc123", "mcp_tools_v1", "production", "v1.1") is None)

# Load from event list.
events = [approval_event, revocation_event, approval_event]  # re-approve
store2 = load_approval_store_from_events(events)
check("load_from_events: re-approval works",
      store2.lookup("sha256:abc123", "mcp_tools_v1", "production", "v1.1") is not None)

# Multiple approvals for different scopes.
store3 = ApprovalStore()
for ctx in ["prod", "staging", "dev"]:
    evt = build_non_action_event("opaque_artifact_approval", {
        "artifact_identity": "sha256:same",
        "approving_operator": "op",
        "governed_family": "fam",
        "deployment_context": ctx,
        "policy_version": "v1",
    })
    store3.ingest_approval(evt)
check("3 approvals for different contexts",
      len(store3.all_approvals()) == 3)
check("each context independently lookupable",
      all(store3.lookup("sha256:same", "fam", ctx, "v1") is not None for ctx in ["prod", "staging", "dev"]))

# --- Opaque path handler (§8.3) ---

# Scenario 1: Approved artifact.
store4 = ApprovalStore()
artifact = b"approved-script-content"
identity = compute_artifact_identity_prefixed(artifact)
store4.ingest_approval(build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": identity,
    "approving_operator": "admin",
    "governed_family": "fam1",
    "deployment_context": "prod",
    "policy_version": "v1",
}))

result = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {"opaque_artifact_path": "/tmp/script.sh"}},
    artifact_bytes=artifact,
    governed_family="fam1",
    deployment_context="prod",
    policy_version="v1",
    approval_lookup_fn=store4.lookup,
)
check("approved artifact → approved_lookup resolution",
      result["resolution"] == "approved_lookup")
check("approved artifact → approved=True",
      result["approved"] is True)
check("approved artifact → event is valid",
      validate_non_action_event(result["event"])[0])
check("approved artifact → event hash valid",
      verify_non_action_event_hash(result["event"])[0])
check("approved artifact → event resolution is approved_lookup",
      result["event"]["resolution"] == "approved_lookup")

# Scenario 2: Unapproved artifact (restatement not possible → denied).
unapproved_artifact = b"unapproved-script-content"
result2 = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {}},
    artifact_bytes=unapproved_artifact,
    governed_family="fam1",
    deployment_context="prod",
    policy_version="v1",
    approval_lookup_fn=store4.lookup,
)
check("unapproved artifact → denied resolution",
      result2["resolution"] == "denied")
check("unapproved artifact → approved=False",
      result2["approved"] is False)
check("unapproved artifact → restatement attempted",
      result2["restatement"] is not None and result2["restatement"]["possible"] is False)
check("unapproved artifact → event is valid",
      validate_non_action_event(result2["event"])[0])

# Scenario 3: Unverified opaque executable rule (§8.5).
# Same content but wrong scope → treated as unverified.
result3 = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {}},
    artifact_bytes=artifact,  # same bytes as approved
    governed_family="fam1",
    deployment_context="staging",  # different context!
    policy_version="v1",
    approval_lookup_fn=store4.lookup,
)
check("scope mismatch → denied (no path/origin exception)",
      result3["resolution"] == "denied")
check("scope mismatch → same identity computed",
      result3["artifact_identity"] == identity)

# Scenario 4: Opaque action with compound metadata.
result4 = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {}},
    artifact_bytes=artifact,
    governed_family="fam1",
    deployment_context="prod",
    policy_version="v1",
    approval_lookup_fn=store4.lookup,
    compound_metadata={
        "compound_action_id": "compound-opaque-1",
        "depends_on": [{"step_id": "setup", "dependency_type": "state"}],
    },
)
check("opaque with compound metadata → event has compound_metadata",
      result4["event"].get("compound_metadata") is not None)
check("opaque with compound metadata → valid event",
      validate_non_action_event(result4["event"])[0])

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
# 2. Chain integrity: opaque_invocation_decision events in a mixed chain
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: chain integrity with opaque events ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import subprocess
import sys
import os
import hashlib

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from event_model import build_non_action_event
from transparency import handle_opaque_action, compute_artifact_identity_prefixed
from approval_store import ApprovalStore

# Generate a fresh action record using policy-eval.
intent = {
    "tool": "FS_WRITE",
    "args": {
        "path": os.path.join(root, "out", "test_chain_opaque.txt"),
        "content": "chain-opaque-test",
        "request_executable": False,
    },
    "intent": {
        "goal": "Write test file for opaque chain test",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "expected_outputs": [
            {"ref": "file:path", "value": os.path.join(root, "out", "test_chain_opaque.txt")}
        ],
    },
}

intent_path = os.path.join(tmp, "opaque_chain_intent.json")
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

# Set as chain head.
action_rec["prev_record_hash"] = None
rec_copy = dict(action_rec)
rec_copy["record_hash"] = None
rec_copy["signature"] = None
canonical = json.dumps(rec_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
action_rec["record_hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# Add approval event.
approval_event = build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": "sha256:deadbeef",
    "approving_operator": "admin",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "prod",
    "policy_version": "v1",
}, prev_record_hash=action_rec["record_hash"])

# Simulate opaque path handling — approved lookup.
store = ApprovalStore()
store.ingest_approval(approval_event)
artifact = b"opaque-approved-content"
# Build the right identity.
identity = compute_artifact_identity_prefixed(artifact)
store2 = ApprovalStore()
store2.ingest_approval(build_non_action_event("opaque_artifact_approval", {
    "artifact_identity": identity,
    "approving_operator": "admin",
    "governed_family": "mcp_tools_v1",
    "deployment_context": "prod",
    "policy_version": "v1",
}))

opaque_result = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {}},
    artifact_bytes=artifact,
    governed_family="mcp_tools_v1",
    deployment_context="prod",
    policy_version="v1",
    approval_lookup_fn=store2.lookup,
    prev_record_hash=approval_event["record_hash"],
)

# Unapproved opaque → denied.
unapproved_result = handle_opaque_action(
    request={"tool": "RUN_SCRIPT", "args": {}},
    artifact_bytes=b"unapproved-content",
    governed_family="mcp_tools_v1",
    deployment_context="prod",
    policy_version="v1",
    approval_lookup_fn=store2.lookup,
    prev_record_hash=opaque_result["event"]["record_hash"],
)

# Write as JSONL chain: action → approval → approved_opaque → denied_opaque.
chain_path = os.path.join(tmp, "opaque_mixed_chain.jsonl")
with open(chain_path, "w") as f:
    for rec in [action_rec, approval_event, opaque_result["event"], unapproved_result["event"]]:
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")

print(f"wrote {chain_path}")
PYEOF

CHAIN_OUT=$(python3 "$ROOT/scripts/verify-chain.py" "$TMP_BASE/opaque_mixed_chain.jsonl" 2>&1) || true
if echo "$CHAIN_OUT" | grep -q "PASS: chain verified"; then
  pass "mixed chain with opaque events verifies"
  if echo "$CHAIN_OUT" | grep -q "1 action, 3 non-action"; then
    pass "chain reports correct action/non-action counts"
  else
    fail "chain count mismatch: $CHAIN_OUT"
  fi
else
  fail "chain verification failed: $CHAIN_OUT"
fi

# ---------------------------------------------------------------------------
# 3. Replay: opaque_invocation_decision events are skipped
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: replay skips opaque events ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os
sys.path.insert(0, os.path.join(sys.argv[1], "scripts"))
from event_model import build_non_action_event

evt = build_non_action_event("opaque_invocation_decision", {
    "artifact_identity": "sha256:abc",
    "governed_family": "fam",
    "resolution": "approved_lookup",
})
path = os.path.join(sys.argv[2], "opaque_decision_event.json")
with open(path, "w") as f:
    json.dump(evt, f, indent=2)
PYEOF

REPLAY_OUT=$(python3 "$ROOT/scripts/replay-record.py" "$TMP_BASE/opaque_decision_event.json" 2>&1) || true
if echo "$REPLAY_OUT" | grep -q "SKIP:"; then
  pass "replay skips opaque_invocation_decision event"
else
  fail "replay did not skip opaque event: $REPLAY_OUT"
fi

# ---------------------------------------------------------------------------
# 4. Transparent fast path unchanged
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: transparent fast path unchanged ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import subprocess
import sys
import os

root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from transparency import classify_action_transparency

with open(os.path.join(root, "capabilities", "capability-registry.json")) as f:
    registry = json.load(f)

# Generate a transparent action and ensure policy-eval handles it normally.
intent = {
    "tool": "FS_WRITE",
    "args": {
        "path": os.path.join(root, "out", "transparent_test.txt"),
        "content": "transparent-path-test",
        "request_executable": False,
    },
    "intent": {
        "goal": "Test transparent fast path",
        "constraints": {"overwrite": False},
        "requested_action": "FS_WRITE",
        "expected_outputs": [
            {"ref": "file:path", "value": os.path.join(root, "out", "transparent_test.txt")}
        ],
    },
}

# Verify classification.
classification = classify_action_transparency(intent, registry)
if classification != "transparent":
    print(f"FAIL: FS_WRITE classified as {classification}")
    sys.exit(1)
print("  PASS: FS_WRITE classified as transparent")

# Run through policy-eval — must work exactly as before.
intent_path = os.path.join(tmp, "transparent_intent.json")
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
    print(f"FAIL: policy-eval failed for transparent action: {result.stderr}")
    sys.exit(1)

rec = json.loads(result.stdout)
if rec.get("policy_decision") != "ALLOW":
    print(f"FAIL: expected ALLOW, got {rec.get('policy_decision')}")
    sys.exit(1)
print("  PASS: transparent action processed by policy-eval as ALLOW")
PYEOF

if [ $? -eq 0 ]; then
  pass "transparent fast path works unchanged"
else
  fail "transparent fast path broken"
fi

# ---------------------------------------------------------------------------
# 5. Approval store from chain file
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: approval store from chain ---"

python3 - "$ROOT" "$TMP_BASE" <<'PYEOF'
import json
import sys
import os
sys.path.insert(0, os.path.join(sys.argv[1], "scripts"))
from approval_store import load_approval_store_from_chain

# The opaque_mixed_chain.jsonl has an approval event in it.
store = load_approval_store_from_chain(os.path.join(sys.argv[2], "opaque_mixed_chain.jsonl"))
approvals = store.all_approvals()
if len(approvals) >= 1:
    print("  PASS: approval store loaded from chain file")
else:
    print(f"  FAIL: expected >=1 approval, got {len(approvals)}")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
  pass "approval store from chain"
else
  fail "approval store from chain"
fi

# ---------------------------------------------------------------------------
# 6. Backward compatibility: W1 tests still pass
# ---------------------------------------------------------------------------
echo ""
echo "--- Backward compatibility: W1 event model tests ---"

W1_OUT=$(bash "$ROOT/system/tests/test_event_model_extension.sh" 2>&1) || true
if echo "$W1_OUT" | grep -q "0 failed"; then
  pass "W1 event model tests still pass"
else
  fail "W1 event model tests broken"
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
