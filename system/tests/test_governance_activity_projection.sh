#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_governance_activity_projection"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

PASS=0
FAIL=0

pass_test() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail_test() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Governance Activity Projection Tests ==="

# ---------------------------------------------------------------------------
# 1. Populated chain — all 5 event categories
# ---------------------------------------------------------------------------
echo ""
echo "--- Populated chain: all 5 event categories ---"

UNIT1_OUT="$TMP_ROOT/unit1.txt"
python3 - "$ROOT" "$TMP_ROOT/populated" > "$UNIT1_OUT" <<'PYEOF'
import json, sys, os
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

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# --- Generate events for all 5 categories ---
# 1. verification_transition: certify_surface
certify_event = server.certify_surface("test_family")

# 2. action_decision: transparent write
target = tmp / "transparent.txt"
res = server.fs_write(str(target), "hello", overwrite=False)

# 3. opaque_approval
artifact = tmp / "test.opaque"
artifact.write_bytes(b"opaque-content-123")
identity = compute_artifact_identity_prefixed(artifact.read_bytes())
approval_event = server.approve_artifact(identity, "test_op")

# 4. opaque_invocation_decision (approved)
def write_action(_rec, args):
    p = Path(args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"], encoding="utf-8")
    return {"write_result": {"bytes_written": len(args["content"].encode("utf-8")), "canonical_path": str(p.resolve())}}

approved_target = tmp / "approved.txt"
approved = server.governed_tool(
    "FS_WRITE",
    {"path": str(approved_target), "content": "ok", "overwrite": False,
     "opaque_artifact_path": str(artifact), "opaque_executable": True},
    {"goal": "test", "constraints": {}, "requested_action": "FS_WRITE",
     "inputs": [], "expected_outputs": [{"ref": "file:path", "value": str(approved_target)}]},
    write_action,
)

# 5. opaque_invocation_decision (denied)
denied_artifact = tmp / "denied.opaque"
denied_artifact.write_bytes(b"denied-content")
denied_target = tmp / "denied.txt"
denied = server.governed_tool(
    "FS_WRITE",
    {"path": str(denied_target), "content": "no", "overwrite": False,
     "opaque_artifact_path": str(denied_artifact), "opaque_executable": True},
    {"goal": "test", "constraints": {}, "requested_action": "FS_WRITE",
     "inputs": [], "expected_outputs": [{"ref": "file:path", "value": str(denied_target)}]},
    write_action,
)

# 6. opaque_revocation
server.revoke_artifact(identity, "test_op")

# 7. verification_transition: report_drift
drift_event = server.report_drift("test_family")

# --- Test governance_activity ---
activity = server.governance_activity()

t("returns entries list", isinstance(activity["entries"], list))
t("has chain_event_count", activity["chain_event_count"] > 0)
t("has total_matching", activity["total_matching"] > 0)
t("has timestamp_utc", bool(activity["timestamp_utc"]))
t("has window dict", isinstance(activity["window"], dict))
t("has filters dict", isinstance(activity["filters"], dict))

# Check all 5 categories are present
categories_found = set(e["event_category"] for e in activity["entries"])
t("has action_decision", "action_decision" in categories_found)
t("has verification_transition", "verification_transition" in categories_found)
t("has opaque_approval", "opaque_approval" in categories_found)
t("has opaque_revocation", "opaque_revocation" in categories_found)
t("has opaque_invocation_decision", "opaque_invocation_decision" in categories_found)

# Check reverse chronological order (most recent first)
positions = [e["sequence_position"] for e in activity["entries"]]
t("reverse chronological order", positions == sorted(positions, reverse=True))

# Check each entry has required fields
for e in activity["entries"]:
    assert "sequence_position" in e
    assert "timestamp_utc" in e
    assert "event_category" in e
    assert "governed_family" in e
    assert "summary" in e
    assert "evidence" in e
    assert "detail" in e
t("all entries have required fields", True)

# Check evidence fields
for e in activity["entries"]:
    ev = e["evidence"]
    if e["event_category"] == "action_decision":
        assert "request_id" in ev, f"action_decision missing request_id: {ev}"
    else:
        assert "event_id" in ev, f"{e['event_category']} missing event_id: {ev}"
    assert "record_hash" in ev, f"{e['event_category']} missing record_hash: {ev}"
t("evidence fields correct per category", True)

# Check summary format for each category
for e in activity["entries"]:
    s = e["summary"]
    cat = e["event_category"]
    if cat == "action_decision":
        assert "\u2192" in s, f"action_decision summary missing arrow: {s}"
    elif cat == "verification_transition":
        assert "\u2192" in s, f"verification_transition summary missing arrow: {s}"
    elif cat == "opaque_approval":
        assert s.startswith("approve "), f"opaque_approval summary wrong prefix: {s}"
    elif cat == "opaque_revocation":
        assert s.startswith("revoke "), f"opaque_revocation summary wrong prefix: {s}"
    elif cat == "opaque_invocation_decision":
        assert s.startswith("opaque invocation"), f"opaque_invocation_decision summary wrong: {s}"
t("summary format correct per category", True)

# Check detail fields per category
for e in activity["entries"]:
    d = e["detail"]
    cat = e["event_category"]
    if cat == "action_decision":
        assert "tool_name" in d and "policy_decision" in d and "record_type" in d
    elif cat == "verification_transition":
        assert "from_state" in d and "to_state" in d and "governed_family" in d
    elif cat in ("opaque_approval", "opaque_revocation"):
        assert "artifact_identity" in d and "operator" in d and "governed_family" in d
    elif cat == "opaque_invocation_decision":
        assert "artifact_identity" in d and "resolution" in d and "governed_family" in d
t("detail fields correct per category", True)

# Cross-reference: drift event_id from report_drift should appear in GAP
drift_event_id = drift_event["event_id"]
gap_event_ids = [e["evidence"].get("event_id") for e in activity["entries"]]
t("drift event_id in GAP", drift_event_id in gap_event_ids)

# Cross-reference with governance_verification
verification = server.governance_verification()
last_transition_id = verification["surfaces"]["test_family"]["last_transition_event_id"]
t("GASR verification last_transition_event_id in GAP", last_transition_id in gap_event_ids)

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
# 2. Empty chain
# ---------------------------------------------------------------------------
echo ""
echo "--- Empty chain ---"

UNIT2_OUT="$TMP_ROOT/unit2.txt"
python3 - "$ROOT" "$TMP_ROOT/empty" > "$UNIT2_OUT" <<'PYEOF'
import os, sys
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

results = []
def t(name, cond):
    results.append((name, bool(cond)))

activity = server.governance_activity()
t("empty: entries is empty list", activity["entries"] == [])
t("empty: chain_event_count is 0", activity["chain_event_count"] == 0)
t("empty: total_matching is 0", activity["total_matching"] == 0)
t("empty: no error", True)

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
# 3. Window controls (limit, offset)
# ---------------------------------------------------------------------------
echo ""
echo "--- Window controls ---"

UNIT3_OUT="$TMP_ROOT/unit3.txt"
python3 - "$ROOT" "$TMP_ROOT/window" > "$UNIT3_OUT" <<'PYEOF'
import os, sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "window_fam"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "ctx"
os.environ["GOV_POLICY_VERSION"] = "v1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Generate several events
server.certify_surface("window_fam")
for i in range(5):
    target = tmp / f"file_{i}.txt"
    server.fs_write(str(target), f"content_{i}", overwrite=False)

# All events
all_activity = server.governance_activity(limit=100)
total = all_activity["total_matching"]
t("window: total > 5", total > 5)

# Limit
limited = server.governance_activity(limit=2)
t("window: limit=2 returns 2", len(limited["entries"]) == 2)
t("window: limit=2 total_matching unchanged", limited["total_matching"] == total)

# Offset
offset_result = server.governance_activity(limit=2, offset=2)
t("window: offset=2 returns 2", len(offset_result["entries"]) == 2)

# Offset + limit should give different entries
limited_positions = [e["sequence_position"] for e in limited["entries"]]
offset_positions = [e["sequence_position"] for e in offset_result["entries"]]
t("window: offset gives different entries", set(limited_positions).isdisjoint(set(offset_positions)))

# Offset beyond total
beyond = server.governance_activity(limit=50, offset=1000)
t("window: offset beyond total returns empty", len(beyond["entries"]) == 0)

# Limit=0 returns empty
zero = server.governance_activity(limit=0)
t("window: limit=0 returns empty", len(zero["entries"]) == 0)

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
# 4. Filter controls
# ---------------------------------------------------------------------------
echo ""
echo "--- Filter controls ---"

UNIT4_OUT="$TMP_ROOT/unit4.txt"
python3 - "$ROOT" "$TMP_ROOT/filter" > "$UNIT4_OUT" <<'PYEOF'
import os, sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "filter_fam"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "ctx"
os.environ["GOV_POLICY_VERSION"] = "v1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server
from transparency import compute_artifact_identity_prefixed

results = []
def t(name, cond):
    results.append((name, bool(cond)))

# Generate mixed events
server.certify_surface("filter_fam")
target = tmp / "f.txt"
server.fs_write(str(target), "data", overwrite=False)

artifact = tmp / "artifact.bin"
artifact.write_bytes(b"filter-test")
identity = compute_artifact_identity_prefixed(artifact.read_bytes())
server.approve_artifact(identity, "op")

# denied opaque invocation
def write_action(_rec, args):
    p = Path(args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"], encoding="utf-8")
    return {"write_result": {"bytes_written": len(args["content"].encode("utf-8")), "canonical_path": str(p.resolve())}}

denied_art = tmp / "denied.bin"
denied_art.write_bytes(b"nope")
denied_target = tmp / "denied.txt"
server.governed_tool(
    "FS_WRITE",
    {"path": str(denied_target), "content": "no", "overwrite": False,
     "opaque_artifact_path": str(denied_art), "opaque_executable": True},
    {"goal": "test", "constraints": {}, "requested_action": "FS_WRITE",
     "inputs": [], "expected_outputs": []},
    write_action,
)

# Filter by event_category
actions_only = server.governance_activity(event_category="action_decision")
t("filter: event_category=action_decision",
  all(e["event_category"] == "action_decision" for e in actions_only["entries"]))
t("filter: at least 1 action", len(actions_only["entries"]) >= 1)

verifications = server.governance_activity(event_category="verification_transition")
t("filter: event_category=verification_transition",
  all(e["event_category"] == "verification_transition" for e in verifications["entries"]))
t("filter: at least 1 verification", len(verifications["entries"]) >= 1)

approvals = server.governance_activity(event_category="opaque_approval")
t("filter: event_category=opaque_approval",
  all(e["event_category"] == "opaque_approval" for e in approvals["entries"]))

# Filter by governed_family
by_family = server.governance_activity(governed_family="filter_fam")
t("filter: governed_family=filter_fam",
  all(e["governed_family"] == "filter_fam" for e in by_family["entries"]))

# Filter by non-existent family
no_match = server.governance_activity(governed_family="nonexistent_fam")
t("filter: nonexistent family returns empty", len(no_match["entries"]) == 0)

# Filter by resolution
denied_only = server.governance_activity(resolution="denied")
t("filter: resolution=denied",
  all(e["detail"].get("resolution") == "denied" for e in denied_only["entries"]))
t("filter: at least 1 denied", len(denied_only["entries"]) >= 1)

# Filter by non-matching resolution
no_restatement = server.governance_activity(resolution="transparent_restatement")
t("filter: resolution=transparent_restatement empty", len(no_restatement["entries"]) == 0)

# Conjunctive filter: event_category + governed_family
conjunctive = server.governance_activity(
    event_category="action_decision", governed_family="filter_fam")
t("filter: conjunctive",
  all(e["event_category"] == "action_decision" and e["governed_family"] == "filter_fam"
      for e in conjunctive["entries"]))

# Invalid event_category returns empty (no matching entries)
bad_cat = server.governance_activity(event_category="nonexistent_category")
t("filter: invalid category returns empty", len(bad_cat["entries"]) == 0)

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
# 5. Read-only invariant
# ---------------------------------------------------------------------------
echo ""
echo "--- Read-only invariant ---"

UNIT5_OUT="$TMP_ROOT/unit5.txt"
python3 - "$ROOT" "$TMP_ROOT/readonly" > "$UNIT5_OUT" <<'PYEOF'
import os, sys, hashlib
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "ro_fam"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

results = []
def t(name, cond):
    results.append((name, bool(cond)))

server.certify_surface("ro_fam")
target = tmp / "readonly.txt"
server.fs_write(str(target), "test", overwrite=False)

# Snapshot chain before activity call
chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
chain_before = chain_path.read_bytes()
hash_before = hashlib.sha256(chain_before).hexdigest()

# Call governance_activity multiple times
server.governance_activity()
server.governance_activity(limit=1, offset=0)
server.governance_activity(event_category="action_decision")
server.governance_activity(governed_family="ro_fam")
server.governance_activity(resolution="denied")

# Chain should be unchanged
chain_after = chain_path.read_bytes()
hash_after = hashlib.sha256(chain_after).hexdigest()
t("chain unchanged after activity calls", hash_before == hash_after)

for name, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
PYEOF

while IFS= read -r line; do
    case "$line" in
        PASS:*) pass_test "${line#PASS: }" ;;
        FAIL:*) fail_test "${line#FAIL: }" ;;
    esac
done < "$UNIT5_OUT"

# ---------------------------------------------------------------------------
# 6. Regression: existing GASR tests still pass
# ---------------------------------------------------------------------------
echo ""
echo "--- Regression: existing test suites ---"

bash "$ROOT/system/tests/test_governance_readout_views.sh" > "$TMP_ROOT/regression_readout.txt" 2>&1
if [ $? -eq 0 ]; then
    pass_test "regression: governance readout views tests pass"
else
    fail_test "regression: governance readout views tests"
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
