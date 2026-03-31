#!/usr/bin/env python3
"""Tests for D-034: Observation endpoint and transparency metric."""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
MCP_DIR = REPO / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))


def test_event_model_ungoverned_operation_type():
    """ungoverned_operation_observed is a recognized non-action event type."""
    from event_model import NON_ACTION_EVENT_TYPES, UNGOVERNED_OPERATION_TYPES
    assert "ungoverned_operation_observed" in NON_ACTION_EVENT_TYPES
    assert "read" in UNGOVERNED_OPERATION_TYPES
    assert "write" in UNGOVERNED_OPERATION_TYPES
    assert "execute" in UNGOVERNED_OPERATION_TYPES
    print("PASS: event_model_ungoverned_operation_type")


def test_build_ungoverned_observation_event():
    """build_non_action_event creates valid ungoverned_operation_observed events."""
    from event_model import build_non_action_event, validate_non_action_event

    event = build_non_action_event(
        "ungoverned_operation_observed",
        {
            "operation_type": "read",
            "target": "/some/file.py",
            "source": "test_hook",
        },
    )
    assert event["event_type"] == "ungoverned_operation_observed"
    assert event["operation_type"] == "read"
    assert event["target"] == "/some/file.py"
    assert event["source"] == "test_hook"
    assert event["record_hash"].startswith("sha256:")
    assert event["event_id"]

    ok, err = validate_non_action_event(event)
    assert ok, f"validation failed: {err}"
    print("PASS: build_ungoverned_observation_event")


def test_validate_ungoverned_observation_rejects_bad_type():
    """Validation rejects unknown operation_type values."""
    from event_model import build_non_action_event, validate_non_action_event

    event = build_non_action_event(
        "ungoverned_operation_observed",
        {"operation_type": "read"},
    )
    # Tamper with operation_type after build
    event["operation_type"] = "invalid_op"
    ok, err = validate_non_action_event(event)
    assert not ok
    assert "operation_type" in err
    print("PASS: validate_ungoverned_observation_rejects_bad_type")


def test_verify_ungoverned_observation_hash():
    """Record hash verification works for ungoverned observation events."""
    from event_model import build_non_action_event, verify_non_action_event_hash

    event = build_non_action_event(
        "ungoverned_operation_observed",
        {"operation_type": "write", "source": "test"},
    )
    ok, err = verify_non_action_event_hash(event)
    assert ok, f"hash verification failed: {err}"

    # Tamper
    event["source"] = "tampered"
    ok, err = verify_non_action_event_hash(event)
    assert not ok
    print("PASS: verify_ungoverned_observation_hash")


def test_transparency_metric_no_observations():
    """With no ungoverned observations, observation_data is False."""
    from readout import compute_transparency_metric

    # Simulate chain rows: only governed action records (no event_type)
    rows = [
        {"tool": "FS_READ", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:00:00Z"},
        {"tool": "FS_WRITE", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:01:00Z"},
    ]
    result = compute_transparency_metric(rows)
    assert result["observation_data"] is False
    assert result["governed_operations"] == 2
    assert result["ungoverned_observations"] == 0
    assert result["transparency_pct"] is not None
    print("PASS: transparency_metric_no_observations")


def test_transparency_metric_with_observations():
    """Transparency = governed / (governed + ungoverned)."""
    from readout import compute_transparency_metric

    rows = [
        {"tool": "FS_READ", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:00:00Z"},
        {"tool": "FS_WRITE", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:01:00Z"},
        {"tool": "FS_READ", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:02:00Z"},
        {"event_type": "ungoverned_operation_observed", "operation_type": "read", "timestamp_utc": "2026-03-31T10:03:00Z"},
        {"event_type": "ungoverned_operation_observed", "operation_type": "write", "timestamp_utc": "2026-03-31T10:04:00Z"},
    ]
    result = compute_transparency_metric(rows)
    assert result["observation_data"] is True
    assert result["governed_operations"] == 3
    assert result["ungoverned_observations"] == 2
    assert result["total_observed"] == 5
    # 3 / 5 = 0.6
    assert result["transparency_pct"] == 0.6
    print("PASS: transparency_metric_with_observations")


def test_transparency_metric_time_range_filter():
    """Time-range filtering works on transparency metric."""
    from readout import compute_transparency_metric

    rows = [
        {"tool": "FS_READ", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-30T10:00:00Z"},
        {"event_type": "ungoverned_operation_observed", "operation_type": "read", "timestamp_utc": "2026-03-30T10:01:00Z"},
        {"tool": "FS_READ", "policy_decision": "ALLOW", "timestamp_utc": "2026-03-31T10:00:00Z"},
        {"event_type": "ungoverned_operation_observed", "operation_type": "write", "timestamp_utc": "2026-03-31T10:01:00Z"},
        {"event_type": "ungoverned_operation_observed", "operation_type": "execute", "timestamp_utc": "2026-03-31T10:02:00Z"},
    ]

    # Filter to 2026-03-31 only
    result = compute_transparency_metric(
        rows,
        start_time="2026-03-31T00:00:00Z",
        end_time="2026-03-31T23:59:59Z",
    )
    assert result["governed_operations"] == 1
    assert result["ungoverned_observations"] == 2
    assert result["total_observed"] == 3
    # 1 / 3 ≈ 0.333333
    assert abs(result["transparency_pct"] - 1/3) < 0.001
    print("PASS: transparency_metric_time_range_filter")


def test_transparency_metric_empty_chain():
    """Empty chain returns no data."""
    from readout import compute_transparency_metric

    result = compute_transparency_metric([])
    assert result["observation_data"] is False
    assert result["governed_operations"] == 0
    assert result["ungoverned_observations"] == 0
    assert result["transparency_pct"] is None
    print("PASS: transparency_metric_empty_chain")


def test_activity_view_includes_ungoverned_observations():
    """Governance activity view normalizes ungoverned observation events."""
    from readout import _normalize_activity_entry

    rec = {
        "event_type": "ungoverned_operation_observed",
        "operation_type": "write",
        "target": "/foo/bar.py",
        "source": "claude_code_hook",
        "event_id": "test-id",
        "record_hash": "sha256:abc",
        "timestamp_utc": "2026-03-31T10:00:00Z",
    }
    entry = _normalize_activity_entry(rec, sequence_position=1)
    assert entry is not None
    assert entry["event_category"] == "ungoverned_observation"
    assert "ungoverned write" in entry["summary"]
    assert entry["detail"]["operation_type"] == "write"
    print("PASS: activity_view_includes_ungoverned_observations")


def test_status_record_includes_transparency():
    """assemble_governance_status_record includes transparency_metric."""
    from readout import load_chain_rows, assemble_governance_status_record
    from verification import VerificationStateTracker
    from approval_store import ApprovalStore

    # Use a temp chain with some data
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write a minimal governed action record
        rec = {
            "tool": "FS_READ",
            "capability_class": "FS_READ",
            "policy_decision": "ALLOW",
            "record_type": "pass_decision",
            "record_version": "0.3",
            "request_id": "test-req-1",
            "record_hash": "sha256:dummy1",
            "timestamp_utc": "2026-03-31T10:00:00Z",
            "prev_record_hash": None,
        }
        f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        chain_path = Path(f.name)

    try:
        tracker = VerificationStateTracker()
        store = ApprovalStore()
        result = assemble_governance_status_record(chain_path, tracker, store)
        assert "transparency_metric" in result
        assert result["transparency_metric"]["governed_operations"] == 1
        assert result["transparency_metric"]["ungoverned_observations"] == 0
        print("PASS: status_record_includes_transparency")
    finally:
        chain_path.unlink(missing_ok=True)


def test_all_operation_types_accepted():
    """All defined operation types produce valid events."""
    from event_model import (
        UNGOVERNED_OPERATION_TYPES,
        build_non_action_event,
        validate_non_action_event,
    )

    for op_type in sorted(UNGOVERNED_OPERATION_TYPES):
        event = build_non_action_event(
            "ungoverned_operation_observed",
            {"operation_type": op_type},
        )
        ok, err = validate_non_action_event(event)
        assert ok, f"validation failed for {op_type}: {err}"

    print("PASS: all_operation_types_accepted")


def main():
    test_event_model_ungoverned_operation_type()
    test_build_ungoverned_observation_event()
    test_validate_ungoverned_observation_rejects_bad_type()
    test_verify_ungoverned_observation_hash()
    test_transparency_metric_no_observations()
    test_transparency_metric_with_observations()
    test_transparency_metric_time_range_filter()
    test_transparency_metric_empty_chain()
    test_activity_view_includes_ungoverned_observations()
    test_status_record_includes_transparency()
    test_all_operation_types_accepted()
    print("\nAll D-034 observation endpoint tests passed.")


if __name__ == "__main__":
    main()
