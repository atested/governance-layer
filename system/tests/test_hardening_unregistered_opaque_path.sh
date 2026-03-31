#!/usr/bin/env bash
set -euo pipefail

# Test: Hardening — Unregistered/Unknown Tool Opaque Path (CECIL-T9)
#
# Validates:
#   1. Unknown/unregistered tools reach the opaque slow path
#   2. Unapproved unknown tool → denied opaque_invocation_decision event
#   3. Approved unknown tool → approved_lookup resolution
#   4. Registered transparent tool behavior unchanged
#   5. Registered tool with opaque markers behavior unchanged

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_hardening_unregistered_opaque"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"

PASS=0
FAIL=0

pass_test() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail_test() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Hardening: Unregistered Opaque Path Tests ==="

# ---------------------------------------------------------------------------
# 1. Unit: classify_action_transparency for unregistered tools
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: classification of unregistered tools ---"

UNIT1_OUT="$TMP_BASE/unit1.txt"
python3 - "$ROOT" > "$UNIT1_OUT" <<'PYEOF'
import json, sys, os
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))

from transparency import classify_action_transparency, classify_transparency

results = []
def t(name, cond):
    results.append((name, bool(cond)))

cap_reg_path = os.path.join(root, "capabilities", "capability-registry.json")
with open(cap_reg_path, "r") as f:
    registry = json.load(f)

# Unregistered tool → opaque
req_unknown = {"tool": "UNKNOWN_TOOL_XYZ", "capability_class": "UNKNOWN_TOOL_XYZ", "args": {}}
t("unregistered tool classified as opaque",
  classify_action_transparency(req_unknown, registry) == "opaque")

# Registered tool → transparent
req_known = {"tool": "FS_WRITE", "capability_class": "FS_WRITE", "args": {"path": "/tmp/x", "content": "y"}}
t("registered tool classified as transparent",
  classify_action_transparency(req_known, registry) == "transparent")

# Registered tool with opaque marker → opaque
req_marker = {"tool": "FS_WRITE", "capability_class": "FS_WRITE",
              "args": {"path": "/tmp/x", "content": "y", "opaque_artifact_path": "/art.bin"}}
t("registered tool with opaque marker classified as opaque",
  classify_action_transparency(req_marker, registry) == "opaque")

# Multiple unregistered tools
for tool_name in ["CUSTOM_EXEC", "PLUGIN_RUN", "EXT_INVOKE", ""]:
    req = {"tool": tool_name, "capability_class": tool_name, "args": {}}
    t(f"unregistered '{tool_name}' is opaque",
      classify_action_transparency(req, registry) == "opaque")

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
# 2. Unit: governed_tool flow structure verification
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: governed_tool flow structure ---"

UNIT2_OUT="$TMP_BASE/unit2.txt"
python3 - "$ROOT" > "$UNIT2_OUT" <<'PYEOF'
import sys, os
root = sys.argv[1]

results = []
def t(name, cond):
    results.append((name, bool(cond)))

server_path = os.path.join(root, "mcp", "server.py")
with open(server_path, "r") as f:
    src = f.read()

# Find governed_tool function body
fn_start = src.index("def governed_tool(")
fn_end = src.index("\n@mcp.tool()", fn_start)
fn_body = src[fn_start:fn_end]

# Verify opaque path comes before normalize_args
opaque_block_pos = fn_body.index('if transparency == "opaque":')
normalize_pos = fn_body.index("normalize_args(tool_name, args)")

t("opaque branch before normalize_args",
  opaque_block_pos < normalize_pos)

# Verify opaque path uses dict(args) not normalize_args
opaque_end = fn_body.index("# Transparent path:")
opaque_body = fn_body[opaque_block_pos:opaque_end]
t("opaque path uses dict(args)",
  "norm_args = dict(args)" in opaque_body)
t("opaque path does NOT call normalize_args",
  "normalize_args(" not in opaque_body)

# Verify transparent path still uses normalize_args
transparent_body = fn_body[opaque_end:]
t("transparent path calls normalize_args",
  "normalize_args(tool_name, args)" in transparent_body)

# Verify intent_obj is only built in transparent path (not before opaque)
pre_opaque = fn_body[:opaque_block_pos]
t("intent_obj not built before opaque check",
  "intent_obj" not in pre_opaque)

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
# 3. Integration: unregistered tool reaches opaque path end-to-end
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: unregistered tool → opaque denial ---"

UNIT3_OUT="$TMP_BASE/unit3.txt"
python3 - "$ROOT" "$TMP_BASE" > "$UNIT3_OUT" <<'PYEOF'
import json, sys, os, hashlib
root = sys.argv[1]
tmp = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from transparency import (
    classify_action_transparency,
    handle_opaque_action,
    compute_artifact_identity_prefixed,
)
from approval_store import ApprovalStore
from event_model import validate_non_action_event, verify_non_action_event_hash

results = []
def t(name, cond):
    results.append((name, bool(cond)))

cap_reg_path = os.path.join(root, "capabilities", "capability-registry.json")
with open(cap_reg_path, "r") as f:
    registry = json.load(f)

# --- Simulate unregistered tool arriving at governed_tool ---
tool_name = "CUSTOM_PLUGIN_EXEC"
args = {
    "opaque_executable": True,
    "content": "#!/bin/bash\necho custom plugin",
}
request = {"tool": tool_name, "capability_class": tool_name, "args": dict(args)}

# Step 1: Classification
transparency = classify_action_transparency(request, registry)
t("step1: classified as opaque", transparency == "opaque")

# Step 2: Skip normalization — use raw args (simulating the fix)
norm_args = dict(args)

# Step 3: Load artifact bytes
content = norm_args.get("content", "")
artifact_bytes = content.encode("utf-8") if isinstance(content, str) else b""
t("step3: artifact bytes loaded", len(artifact_bytes) > 0)

# Step 4: Opaque slow path — no approval → denied
store = ApprovalStore()
result = handle_opaque_action(
    request=request,
    artifact_bytes=artifact_bytes,
    governed_family="test_fam",
    deployment_context="test_ctx",
    policy_version="test_v1",
    approval_lookup_fn=store.lookup,
)
t("step4: resolution is denied", result["resolution"] == "denied")
t("step4: approved is False", result["approved"] is False)
t("step4: artifact_identity computed",
  result["artifact_identity"].startswith("sha256:"))
t("step4: event present", result["event"] is not None)

# Validate the event
event = result["event"]
ok, err = validate_non_action_event(event)
t("step4: event validates", ok)
ok, err = verify_non_action_event_hash(event)
t("step4: event hash valid", ok)
t("step4: event type correct",
  event["event_type"] == "opaque_invocation_decision")
t("step4: event resolution is denied",
  event["resolution"] == "denied")

# --- Simulate approved unregistered tool ---
artifact_identity = compute_artifact_identity_prefixed(artifact_bytes)
store2 = ApprovalStore()
store2.ingest_approval({
    "artifact_identity": artifact_identity,
    "approving_operator": "admin",
    "governed_family": "test_fam",
    "deployment_context": "test_ctx",
    "policy_version": "test_v1",
})

result2 = handle_opaque_action(
    request=request,
    artifact_bytes=artifact_bytes,
    governed_family="test_fam",
    deployment_context="test_ctx",
    policy_version="test_v1",
    approval_lookup_fn=store2.lookup,
)
t("approved: resolution is approved_lookup", result2["resolution"] == "approved_lookup")
t("approved: approved is True", result2["approved"] is True)
t("approved: approval_record present", result2["approval_record"] is not None)

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
# 4. Regression: existing test suites
# ---------------------------------------------------------------------------
echo ""
echo "--- Regression: existing test suites ---"

bash "$ROOT/system/tests/test_verification_state_model.sh" > "$TMP_BASE/regression_vsm.txt" 2>&1
if [ $? -eq 0 ]; then
    pass_test "regression: verification state model tests pass"
else
    fail_test "regression: verification state model tests"
fi

bash "$ROOT/system/tests/test_hardening_singleton_consistency.sh" > "$TMP_BASE/regression_hsc.txt" 2>&1
if [ $? -eq 0 ]; then
    pass_test "regression: singleton consistency tests pass"
else
    fail_test "regression: singleton consistency tests"
fi

bash "$ROOT/system/tests/test_event_model_extension.sh" > "$TMP_BASE/regression_em.txt" 2>&1
if [ $? -eq 0 ]; then
    pass_test "regression: event model extension tests pass"
else
    fail_test "regression: event model extension tests"
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
