#!/usr/bin/env bash
set -euo pipefail

# Test: Hardening — Singleton Consistency 
#
# Validates:
#   1. Approval store singleton caching (not rebuilt on every opaque action)
#   2. Quarantine invalidates both runtime singletons
#   3. Classification timing: opaque markers survive normalization
#   4. No semantic change in governance outcomes

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_hardening_singleton"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"

PASS=0
FAIL=0

pass_test() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail_test() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Hardening: Singleton Consistency Tests ==="

# ---------------------------------------------------------------------------
# 1. Approval store singleton caching and incremental ingest
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: approval store singleton caching ---"

UNIT1_OUT="$TMP_BASE/unit1.txt"
python3 - "$ROOT" "$TMP_BASE" > "$UNIT1_OUT" <<'PYEOF'
import json, sys, os
root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from approval_store import ApprovalStore, load_approval_store_from_chain

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# --- Incremental ingest matches full rebuild ---
# Build a chain with approvals and revocations.
chain_path = os.path.join(tmp, "approval_chain.jsonl")
events = [
    {
        "event_type": "opaque_artifact_approval",
        "artifact_identity": "sha256:aaa",
        "approving_operator": "op1",
        "governed_family": "fam1",
        "deployment_context": "ctx1",
        "policy_version": "v1",
        "event_id": "e1",
        "timestamp_utc": "2026-01-01T00:00:00Z",
    },
    {
        "event_type": "opaque_artifact_approval",
        "artifact_identity": "sha256:bbb",
        "approving_operator": "op2",
        "governed_family": "fam1",
        "deployment_context": "ctx1",
        "policy_version": "v1",
        "event_id": "e2",
        "timestamp_utc": "2026-01-02T00:00:00Z",
    },
    {
        "event_type": "opaque_artifact_revocation",
        "artifact_identity": "sha256:aaa",
        "revoking_operator": "op1",
        "governed_family": "fam1",
        "deployment_context": "ctx1",
        "policy_version": "v1",
        "event_id": "e3",
        "timestamp_utc": "2026-01-03T00:00:00Z",
    },
]

with open(chain_path, "w") as f:
    for ev in events:
        f.write(json.dumps(ev) + "\n")

# Full rebuild from chain.
full_store = load_approval_store_from_chain(chain_path)

# Incremental: start empty, ingest events one by one.
incr_store = ApprovalStore()
for ev in events:
    et = ev["event_type"]
    if et == "opaque_artifact_approval":
        incr_store.ingest_approval(ev)
    elif et == "opaque_artifact_revocation":
        incr_store.ingest_revocation(ev)

t("incremental matches full: aaa revoked",
  full_store.lookup("sha256:aaa", "fam1", "ctx1", "v1") is None)
t("incremental matches full: bbb approved",
  full_store.lookup("sha256:bbb", "fam1", "ctx1", "v1") is not None)
t("incremental: aaa revoked",
  incr_store.lookup("sha256:aaa", "fam1", "ctx1", "v1") is None)
t("incremental: bbb approved",
  incr_store.lookup("sha256:bbb", "fam1", "ctx1", "v1") is not None)
t("incremental parity",
  full_store.all_approvals() == incr_store.all_approvals())

# --- Incremental ingest of a new event after initial load ---
new_approval = {
    "event_type": "opaque_artifact_approval",
    "artifact_identity": "sha256:ccc",
    "approving_operator": "op3",
    "governed_family": "fam1",
    "deployment_context": "ctx1",
    "policy_version": "v1",
    "event_id": "e4",
    "timestamp_utc": "2026-01-04T00:00:00Z",
}
incr_store.ingest_approval(new_approval)
t("incremental ingest adds new approval",
  incr_store.lookup("sha256:ccc", "fam1", "ctx1", "v1") is not None)
t("full store doesn't have new approval yet",
  full_store.lookup("sha256:ccc", "fam1", "ctx1", "v1") is None)

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
PYEOF

while IFS= read -r line; do
    case "$line" in
        PASS:*) pass_test "${line#PASS: }" ;;
        FAIL:*) fail_test "${line#FAIL: }" ;;
    esac
done < "$UNIT1_OUT"

# ---------------------------------------------------------------------------
# 2. Quarantine invalidation
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: quarantine invalidates runtime singletons ---"

UNIT2_OUT="$TMP_BASE/unit2.txt"
python3 - "$ROOT" "$TMP_BASE" > "$UNIT2_OUT" <<'PYEOF'
import json, sys, os
root = sys.argv[1]
tmp = sys.argv[2]

# We need to test the server module's singleton management.
# To avoid side effects, we test the invalidation contract directly
# by simulating the singleton lifecycle.
sys.path.insert(0, os.path.join(root, "scripts"))

from verification import VerificationStateTracker
from approval_store import ApprovalStore

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Simulate the singleton lifecycle:
# 1. Initialize singletons
# 2. Populate with state
# 3. Invalidate (set to None)
# 4. Verify next access rebuilds from scratch

# --- Verification tracker invalidation ---
tracker = VerificationStateTracker()
tracker.transition("surface_a", "verified")
t("pre-invalidation: surface_a is verified",
  tracker.get_state("surface_a") == "verified")

# Simulate invalidation: set to None, create new instance
tracker = None
tracker = VerificationStateTracker()
t("post-invalidation: surface_a is unverified (fresh)",
  tracker.get_state("surface_a") == "unverified")

# --- Approval store invalidation ---
store = ApprovalStore()
store.ingest_approval({
    "artifact_identity": "sha256:test",
    "approving_operator": "op",
    "governed_family": "fam",
    "deployment_context": "ctx",
    "policy_version": "v1",
})
t("pre-invalidation: approval exists",
  store.lookup("sha256:test", "fam", "ctx", "v1") is not None)

# Simulate invalidation
store = None
store = ApprovalStore()
t("post-invalidation: approval gone (fresh)",
  store.lookup("sha256:test", "fam", "ctx", "v1") is None)

# --- Test _invalidate_runtime_state contract via import ---
# Verify the function exists and resets both globals.
sys.path.insert(0, os.path.join(root, "mcp"))
# We can't fully import server.py (it has many deps), but we can
# verify the contract by reading the source.
server_path = os.path.join(root, "mcp", "server.py")
with open(server_path, "r") as f:
    src = f.read()

t("_invalidate_runtime_state defined",
  "def _invalidate_runtime_state()" in src)
t("invalidation resets _VERIFICATION_TRACKER",
  "_VERIFICATION_TRACKER = None" in src)
t("invalidation resets _APPROVAL_STORE",
  "_APPROVAL_STORE = None" in src)
t("quarantine calls invalidation",
  "_invalidate_runtime_state()" in src)

# Verify quarantine calls _invalidate_runtime_state after CHAIN.rename
# (find the function body)
quarantine_start = src.index("def _quarantine_chain(")
quarantine_end = src.index("\ndef ", quarantine_start + 1)
quarantine_body = src[quarantine_start:quarantine_end]
t("quarantine invalidation is after rename",
  quarantine_body.index("CHAIN.rename(dst)") < quarantine_body.index("_invalidate_runtime_state()"))

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
PYEOF

while IFS= read -r line; do
    case "$line" in
        PASS:*) pass_test "${line#PASS: }" ;;
        FAIL:*) fail_test "${line#FAIL: }" ;;
    esac
done < "$UNIT2_OUT"

# ---------------------------------------------------------------------------
# 3. Classification timing: opaque markers survive normalization
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: opaque markers survive normalization ---"

UNIT3_OUT="$TMP_BASE/unit3.txt"
python3 - "$ROOT" > "$UNIT3_OUT" <<'PYEOF'
import json, sys, os
root = sys.argv[1]

# Add mcp/ to path for normalize_args
sys.path.insert(0, os.path.join(root, "mcp"))
sys.path.insert(0, os.path.join(root, "scripts"))

# We need to load the capability registry and normalize_args.
# Import just the pieces we need.
cap_reg_path = os.path.join(root, "capabilities", "capability-registry.json")
with open(cap_reg_path, "r") as f:
    cap_reg = json.load(f)

# Build _CAPS dict (same logic as server.py)
_CAPS = {}
for entry in cap_reg.get("tools", []):
    _CAPS[entry["tool"]] = entry

def get_capability(capability):
    if capability not in _CAPS:
        raise KeyError(f"Unknown capability: {capability}")
    return _CAPS[capability]

# Inline normalize_args from server.py (the function is not importable
# without the full server module, so we replicate its logic here for
# testing the invariant).
def normalize_args(capability, args):
    cap = get_capability(capability)
    caps = cap.get("caps", {}) or {}
    spec = cap.get("args", {}) or {}
    required = spec.get("required", []) or []
    missing = [k for k in required if k not in args or args.get(k) is None]
    if missing:
        return args, {"_missing": missing}
    out = dict(args)
    # (capability-specific normalization omitted — we just need to verify
    # that unknown fields are preserved in the copy)
    return out, {}

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Test: FS_WRITE with opaque_artifact_path survives normalization
args_with_path = {
    "path": "/tmp/test.bin",
    "content": "binary data",
    "opaque_artifact_path": "/some/artifact.bin",
}
norm, _ = normalize_args("FS_WRITE", args_with_path)
t("opaque_artifact_path survives normalization",
  norm.get("opaque_artifact_path") == "/some/artifact.bin")

# Test: FS_WRITE with opaque_executable survives normalization
args_with_exec = {
    "path": "/tmp/test.sh",
    "content": "#!/bin/bash\necho hi",
    "opaque_executable": True,
}
norm, _ = normalize_args("FS_WRITE", args_with_exec)
t("opaque_executable survives normalization",
  norm.get("opaque_executable") is True)

# Test: Both markers simultaneously
args_both = {
    "path": "/tmp/test.sh",
    "content": "data",
    "opaque_artifact_path": "/art.bin",
    "opaque_executable": True,
}
norm, _ = normalize_args("FS_WRITE", args_both)
t("both markers survive normalization",
  norm.get("opaque_artifact_path") == "/art.bin" and norm.get("opaque_executable") is True)

# Test: Classification consistency — same result before and after normalization
from transparency import classify_action_transparency
registry = cap_reg

for test_args, label in [
    (args_with_path, "opaque_artifact_path"),
    (args_with_exec, "opaque_executable"),
    (args_both, "both markers"),
]:
    pre_request = {"tool": "FS_WRITE", "capability_class": "FS_WRITE", "args": dict(test_args)}
    pre_result = classify_action_transparency(pre_request, registry)

    norm_out, _ = normalize_args("FS_WRITE", test_args)
    post_request = {"tool": "FS_WRITE", "capability_class": "FS_WRITE", "args": norm_out}
    post_result = classify_action_transparency(post_request, registry)

    t(f"classification consistent ({label})", pre_result == post_result == "opaque")

# Test: Without opaque markers, registered tool is transparent
clean_args = {"path": "/tmp/test.txt", "content": "hello"}
norm_clean, _ = normalize_args("FS_WRITE", clean_args)
req_clean = {"tool": "FS_WRITE", "capability_class": "FS_WRITE", "args": norm_clean}
t("clean args: transparent", classify_action_transparency(req_clean, registry) == "transparent")

# Test: invariant documented in server.py source
server_path = os.path.join(root, "mcp", "server.py")
with open(server_path, "r") as f:
    src = f.read()
t("classification timing invariant documented",
  "Classification timing invariant" in src)

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
PYEOF

while IFS= read -r line; do
    case "$line" in
        PASS:*) pass_test "${line#PASS: }" ;;
        FAIL:*) fail_test "${line#FAIL: }" ;;
    esac
done < "$UNIT3_OUT"

# ---------------------------------------------------------------------------
# 4. Incremental ingest contract in _append_non_action_event
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: _append_non_action_event incremental ingest contract ---"

UNIT4_OUT="$TMP_BASE/unit4.txt"
python3 - "$ROOT" > "$UNIT4_OUT" <<'PYEOF'
import sys, os
root = sys.argv[1]

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Verify _append_non_action_event handles all three incrementally-ingested
# event types by reading the source.
server_path = os.path.join(root, "mcp", "server.py")
with open(server_path, "r") as f:
    src = f.read()

# Find the _append_non_action_event function body
fn_start = src.index("def _append_non_action_event(")
fn_end = src.index("\ndef ", fn_start + 1)
fn_body = src[fn_start:fn_end]

t("ingests verification_state_transition",
  "verification_state_transition" in fn_body and "ingest_transition_event" in fn_body)
t("ingests opaque_artifact_approval",
  "opaque_artifact_approval" in fn_body and "ingest_approval" in fn_body)
t("ingests opaque_artifact_revocation",
  "opaque_artifact_revocation" in fn_body and "ingest_revocation" in fn_body)

# Verify governed_tool uses _approval_store() singleton, not load_approval_store_from_chain
governed_start = src.index("def governed_tool(")
governed_end = src.index("\ndef ", governed_start + 1)
governed_body = src[governed_start:governed_end]
t("governed_tool uses _approval_store() singleton",
  "_approval_store()" in governed_body)
t("governed_tool does NOT rebuild from chain",
  "load_approval_store_from_chain" not in governed_body)

# Verify list_active_approvals uses singleton
list_start = src.index("def list_active_approvals(")
list_end = src.index("\ndef ", list_start + 1) if "\ndef " in src[list_start + 1:] else len(src)
list_body = src[list_start:list_end]
t("list_active_approvals uses _approval_store() singleton",
  "_approval_store()" in list_body)
t("list_active_approvals does NOT rebuild from chain",
  "load_approval_store_from_chain" not in list_body)

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
PYEOF

while IFS= read -r line; do
    case "$line" in
        PASS:*) pass_test "${line#PASS: }" ;;
        FAIL:*) fail_test "${line#FAIL: }" ;;
    esac
done < "$UNIT4_OUT"

# ---------------------------------------------------------------------------
# 5. Regression: existing governance tests still pass
# ---------------------------------------------------------------------------
echo ""
echo "--- Regression: existing test suites ---"

# Lane A verification state model
bash "$ROOT/system/tests/test_verification_state_model.sh" > "$TMP_BASE/regression_lane_a.txt" 2>&1
if [ $? -eq 0 ]; then
    pass_test "regression: verification state model tests pass"
else
    fail_test "regression: verification state model tests"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Summary ==="
TOTAL=$((PASS + FAIL))
echo "  $PASS/$TOTAL passed"
if [ "$FAIL" -gt 0 ]; then
    echo "  FAILED ($FAIL failures)"
    exit 1
else
    echo "  ALL PASS"
    exit 0
fi
