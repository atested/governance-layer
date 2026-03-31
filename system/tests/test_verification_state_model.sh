#!/usr/bin/env bash
set -euo pipefail

# Test: Verification State Model 
#
# Validates:
#   1. VerificationStateTracker — valid transitions, invalid transition rejection
#   2. Default state for unknown surfaces is 'unverified'
#   3. ProbeResult contract and evaluate_probe_result() logic
#   4. Chain-derived state reconstruction round-trip
#   5. Transition event production (record_hash, event structure)
#   6. Routing hook contract (check_verification_state)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_verification_state_model"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"

PASS=0
FAIL=0

pass_test() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail_test() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Verification State Model Tests ==="

# ---------------------------------------------------------------------------
# 1. Unit tests: tracker + transitions + routing hook
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: VerificationStateTracker ---"

UNIT1_OUT="$TMP_BASE/unit1.txt"
python3 - "$ROOT" > "$UNIT1_OUT" <<'PYEOF'
import sys, os
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))

from verification import (
    VerificationStateTracker,
    is_valid_transition,
    VALID_TRANSITIONS,
    check_verification_state,
)
from event_model import verify_non_action_event_hash, validate_non_action_event

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# --- Valid transition graph ---
t("valid: unverified→verified", is_valid_transition("unverified", "verified"))
t("valid: verified→drift_detected", is_valid_transition("verified", "drift_detected"))
t("valid: drift_detected→verified", is_valid_transition("drift_detected", "verified"))
t("valid: drift_detected→unverified", is_valid_transition("drift_detected", "unverified"))

# --- Invalid transitions ---
t("invalid: unverified→drift_detected", not is_valid_transition("unverified", "drift_detected"))
t("invalid: verified→unverified", not is_valid_transition("verified", "unverified"))
t("invalid: unverified→unverified", not is_valid_transition("unverified", "unverified"))
t("invalid: verified→verified", not is_valid_transition("verified", "verified"))

# --- Tracker: default state ---
tracker = VerificationStateTracker()
t("default state is unverified", tracker.get_state("test_family") == "unverified")
t("default state for random surface", tracker.get_state("xyz_unknown") == "unverified")

# --- Tracker: valid transition produces event ---
tracker = VerificationStateTracker()
event = tracker.transition("family_a", "verified")
t("transition returns event", isinstance(event, dict))
t("event_type correct", event["event_type"] == "verification_state_transition")
t("from_state is unverified", event["from_state"] == "unverified")
t("to_state is verified", event["to_state"] == "verified")
t("governed_family in event", event["governed_family"] == "family_a")
t("record_hash present", event["record_hash"].startswith("sha256:"))
t("state updated after transition", tracker.get_state("family_a") == "verified")

# --- Tracker: hash verification ---
ok, err = verify_non_action_event_hash(event)
t("event hash verifies", ok)

# --- Tracker: event validates ---
ok, err = validate_non_action_event(event)
t("event validates", ok)

# --- Tracker: chain of transitions ---
tracker = VerificationStateTracker()
e1 = tracker.transition("surf_x", "verified")
e2 = tracker.transition("surf_x", "drift_detected", prev_record_hash=e1["record_hash"])
e3 = tracker.transition("surf_x", "verified", prev_record_hash=e2["record_hash"])
t("chain: final state is verified", tracker.get_state("surf_x") == "verified")
t("chain: prev_record_hash links", e2["prev_record_hash"] == e1["record_hash"])
t("chain: e3 links to e2", e3["prev_record_hash"] == e2["record_hash"])

# --- Tracker: drift_detected → unverified ---
tracker = VerificationStateTracker()
tracker.transition("s1", "verified")
tracker.transition("s1", "drift_detected")
e = tracker.transition("s1", "unverified")
t("drift→unverified works", tracker.get_state("s1") == "unverified")
t("drift→unverified event from_state", e["from_state"] == "drift_detected")

# --- Tracker: invalid transition raises ---
tracker = VerificationStateTracker()
try:
    tracker.transition("bad", "drift_detected")
    t("invalid transition raises", False)
except ValueError:
    t("invalid transition raises", True)

# --- Tracker: no-op transition raises ---
tracker = VerificationStateTracker()
tracker.transition("noop_test", "verified")
try:
    tracker.transition("noop_test", "verified")
    t("no-op transition raises", False)
except ValueError:
    t("no-op transition raises", True)

# --- Tracker: verified → unverified is invalid ---
tracker = VerificationStateTracker()
tracker.transition("v2u", "verified")
try:
    tracker.transition("v2u", "unverified")
    t("verified→unverified raises", False)
except ValueError:
    t("verified→unverified raises", True)

# --- Tracker: multiple surfaces independent ---
tracker = VerificationStateTracker()
tracker.transition("alpha", "verified")
tracker.transition("beta", "verified")
tracker.transition("alpha", "drift_detected")
t("multi: alpha is drift_detected", tracker.get_state("alpha") == "drift_detected")
t("multi: beta is verified", tracker.get_state("beta") == "verified")
t("multi: gamma is unverified", tracker.get_state("gamma") == "unverified")

# --- Tracker: all_states ---
states = tracker.all_states()
t("all_states returns dict", isinstance(states, dict))
t("all_states has alpha", states.get("alpha") == "drift_detected")
t("all_states has beta", states.get("beta") == "verified")
t("all_states doesn't have untracked", "gamma" not in states)

# --- Routing hook contract ---
tracker = VerificationStateTracker()
tracker.transition("hook_test", "verified")
t("check_verification_state verified", check_verification_state("hook_test", tracker) == "verified")
t("check_verification_state unverified", check_verification_state("unknown_surf", tracker) == "unverified")

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
# 2. Probe result contract tests
# ---------------------------------------------------------------------------
echo ""
echo "--- Unit: ProbeResult and evaluate_probe_result ---"

UNIT2_OUT="$TMP_BASE/unit2.txt"
python3 - "$ROOT" > "$UNIT2_OUT" <<'PYEOF'
import sys, os
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts"))

from verification import ProbeResult, evaluate_probe_result, VerificationStateTracker

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# --- ProbeResult construction ---
pr = ProbeResult(
    probe_id="probe-001",
    governed_family="test_surface",
    property_tested="registry_integrity",
    evidence={"file_hash": "abc123", "parseable": True},
    passed=True,
    nonce="nonce-42",
    timestamp_utc="2026-03-20T00:00:00Z",
)
t("probe_result: probe_id", pr.probe_id == "probe-001")
t("probe_result: evidence is dict", isinstance(pr.evidence, dict))
t("probe_result: nonce present", pr.nonce == "nonce-42")
t("probe_result: passed is bool", pr.passed is True)

# --- ProbeResult with no nonce ---
pr_no_nonce = ProbeResult(
    probe_id="probe-002",
    governed_family="s1",
    property_tested="test",
    evidence={"obs": 1},
    passed=False,
)
t("probe_result: nonce defaults None", pr_no_nonce.nonce is None)
t("probe_result: timestamp defaults None", pr_no_nonce.timestamp_utc is None)

# --- evaluate_probe_result: passing probe on unverified → verified ---
tracker = VerificationStateTracker()
pr_pass = ProbeResult("p1", "surf_a", "test_prop", {"x": 1}, True)
target = evaluate_probe_result(pr_pass, tracker)
t("eval: pass+unverified→verified", target == "verified")

# --- evaluate_probe_result: passing probe on verified → None ---
tracker = VerificationStateTracker()
tracker.transition("surf_b", "verified")
pr_pass2 = ProbeResult("p2", "surf_b", "test_prop", {"x": 1}, True)
target = evaluate_probe_result(pr_pass2, tracker)
t("eval: pass+verified→None", target is None)

# --- evaluate_probe_result: passing probe on drift_detected → verified ---
tracker = VerificationStateTracker()
tracker.transition("surf_c", "verified")
tracker.transition("surf_c", "drift_detected")
pr_pass3 = ProbeResult("p3", "surf_c", "test_prop", {"x": 1}, True)
target = evaluate_probe_result(pr_pass3, tracker)
t("eval: pass+drift→verified", target == "verified")

# --- evaluate_probe_result: failing probe on verified → drift_detected ---
tracker = VerificationStateTracker()
tracker.transition("surf_d", "verified")
pr_fail = ProbeResult("p4", "surf_d", "test_prop", {"error": "mismatch"}, False)
target = evaluate_probe_result(pr_fail, tracker)
t("eval: fail+verified→drift_detected", target == "drift_detected")

# --- evaluate_probe_result: failing probe on unverified → None ---
tracker = VerificationStateTracker()
pr_fail2 = ProbeResult("p5", "surf_e", "test_prop", {"error": "x"}, False)
target = evaluate_probe_result(pr_fail2, tracker)
t("eval: fail+unverified→None", target is None)

# --- evaluate_probe_result: failing probe on drift_detected → None ---
tracker = VerificationStateTracker()
tracker.transition("surf_f", "verified")
tracker.transition("surf_f", "drift_detected")
pr_fail3 = ProbeResult("p6", "surf_f", "test_prop", {"error": "y"}, False)
target = evaluate_probe_result(pr_fail3, tracker)
t("eval: fail+drift→None", target is None)

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
# 3. Integration: chain reconstruction round-trip
# ---------------------------------------------------------------------------
echo ""
echo "--- Integration: chain reconstruction round-trip ---"

CHAIN_FILE="$TMP_BASE/verification_chain.jsonl"
UNIT3_OUT="$TMP_BASE/unit3.txt"

python3 - "$ROOT" "$CHAIN_FILE" > "$UNIT3_OUT" <<'PYEOF'
import json, sys, os
root = sys.argv[1]
chain_path = sys.argv[2]
sys.path.insert(0, os.path.join(root, "scripts"))

from verification import (
    VerificationStateTracker,
    load_verification_state_from_chain,
    load_verification_state_from_events,
)

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Build a chain with multiple surfaces and transitions.
tracker = VerificationStateTracker()
events = []
e1 = tracker.transition("family_fs", "verified")
events.append(e1)
e2 = tracker.transition("family_net", "verified", prev_record_hash=e1["record_hash"])
events.append(e2)
e3 = tracker.transition("family_fs", "drift_detected", prev_record_hash=e2["record_hash"])
events.append(e3)
e4 = tracker.transition("family_fs", "verified", prev_record_hash=e3["record_hash"])
events.append(e4)
e5 = tracker.transition("family_net", "drift_detected", prev_record_hash=e4["record_hash"])
events.append(e5)
e6 = tracker.transition("family_net", "unverified", prev_record_hash=e5["record_hash"])
events.append(e6)

# Write chain to JSONL.
with open(chain_path, "w", encoding="utf-8") as f:
    for ev in events:
        f.write(json.dumps(ev, sort_keys=True) + "\n")

# Reconstruct from chain file.
reconstructed = load_verification_state_from_chain(chain_path)
t("reconstruct: family_fs is verified", reconstructed.get_state("family_fs") == "verified")
t("reconstruct: family_net is unverified", reconstructed.get_state("family_net") == "unverified")
t("reconstruct: unknown is unverified", reconstructed.get_state("unknown_family") == "unverified")

# Reconstruct from events list.
reconstructed2 = load_verification_state_from_events(events)
t("from_events: family_fs is verified", reconstructed2.get_state("family_fs") == "verified")
t("from_events: family_net is unverified", reconstructed2.get_state("family_net") == "unverified")

# Verify both methods produce same state.
t("reconstruction parity", reconstructed.all_states() == reconstructed2.all_states())

# Chain file with mixed event types (should ignore non-transition events).
mixed_chain = chain_path + ".mixed"
with open(mixed_chain, "w", encoding="utf-8") as f:
    f.write(json.dumps({"event_type": "opaque_artifact_approval", "dummy": True}) + "\n")
    f.write(json.dumps(events[0], sort_keys=True) + "\n")
    f.write(json.dumps({"event_type": "opaque_invocation_decision", "dummy": True}) + "\n")
    f.write(json.dumps(events[1], sort_keys=True) + "\n")

mixed_tracker = load_verification_state_from_chain(mixed_chain)
t("mixed chain: ignores non-transition events", mixed_tracker.get_state("family_fs") == "verified")
t("mixed chain: picks up transition events", mixed_tracker.get_state("family_net") == "verified")
t("mixed chain: only 2 surfaces tracked", len(mixed_tracker.all_states()) == 2)

# Empty chain file.
empty_chain = chain_path + ".empty"
with open(empty_chain, "w") as f:
    pass
empty_tracker = load_verification_state_from_chain(empty_chain)
t("empty chain: no state", len(empty_tracker.all_states()) == 0)
t("empty chain: default unverified", empty_tracker.get_state("anything") == "unverified")

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
