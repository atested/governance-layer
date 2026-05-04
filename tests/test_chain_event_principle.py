"""Tests for D-207: Chain event principle — everything external is recorded.

Verifies:
  1. New event types are in NON_ACTION_EVENT_TYPES
  2. build_non_action_event succeeds for each new type
  3. Hash verification passes for constructed events
  4. dashboard_config_unlocked carries operator_label and tier
  5. report_exported is a valid event type
  6. failed_authentication_attempt carries endpoint and failure_reason
  7. license_validation_attempted carries result and endpoint
  8. trouble_report_submitted carries destination and payload_hash
  9. notification_received is a valid event type
  10. telemetry_opt_in_changed carries previous/new state
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from event_model import (
    NON_ACTION_EVENT_TYPES,
    build_non_action_event,
    verify_non_action_event_hash,
)


# ---------------------------------------------------------------------------
# Event type presence
# ---------------------------------------------------------------------------

D207_EVENT_TYPES = [
    "trouble_report_submitted",
    "report_exported",
    "dashboard_config_unlocked",
    "failed_authentication_attempt",
    "license_validation_attempted",
    "notification_received",
    "telemetry_submitted",
    "telemetry_opt_in_changed",
]


@pytest.mark.parametrize("event_type", D207_EVENT_TYPES)
def test_event_type_in_frozenset(event_type):
    assert event_type in NON_ACTION_EVENT_TYPES


# ---------------------------------------------------------------------------
# Event construction and hash verification
# ---------------------------------------------------------------------------

def test_trouble_report_submitted():
    event = build_non_action_event("trouble_report_submitted", {
        "destination": "https://license.atested.com/api/trouble-report",
        "payload_hash": "sha256:abc123def456",
        "payload_size": 2048,
        "priority": "medium",
    })
    assert event["event_type"] == "trouble_report_submitted"
    assert event["record_hash"].startswith("sha256:")
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_report_exported():
    event = build_non_action_event("report_exported", {
        "report_name": "governance-activity",
        "format": "json",
        "time_range": "2026-04-01/2026-05-01",
        "record_count": 150,
    })
    assert event["event_type"] == "report_exported"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_dashboard_config_unlocked():
    event = build_non_action_event("dashboard_config_unlocked", {
        "operator_label": "Greg K",
        "tier": "crew",
    })
    assert event["event_type"] == "dashboard_config_unlocked"
    assert event["operator_label"] == "Greg K"
    assert event["tier"] == "crew"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_failed_authentication_attempt():
    event = build_non_action_event("failed_authentication_attempt", {
        "endpoint": "/api/export/authorize",
        "failure_reason": "invalid_license_key",
    })
    assert event["event_type"] == "failed_authentication_attempt"
    assert event["endpoint"] == "/api/export/authorize"
    assert event["failure_reason"] == "invalid_license_key"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_license_validation_attempted_success():
    event = build_non_action_event("license_validation_attempted", {
        "result": "success",
        "tier_activated": "crew",
        "endpoint": "/api/config/verify-license",
    })
    assert event["event_type"] == "license_validation_attempted"
    assert event["result"] == "success"
    assert event["tier_activated"] == "crew"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_license_validation_attempted_failure():
    event = build_non_action_event("license_validation_attempted", {
        "result": "failure",
        "tier_activated": None,
        "endpoint": "/api/config/verify-license",
    })
    assert event["result"] == "failure"
    assert event["tier_activated"] is None
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_notification_received():
    event = build_non_action_event("notification_received", {
        "notification_id": "notif-001",
        "notification_type": "system_announcement",
    })
    assert event["event_type"] == "notification_received"
    assert event["notification_type"] == "system_announcement"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_telemetry_submitted():
    event = build_non_action_event("telemetry_submitted", {
        "destination": "https://license.atested.com/api/telemetry",
        "payload_hash": "sha256:deadbeef",
        "payload_size": 4096,
    })
    assert event["event_type"] == "telemetry_submitted"
    assert event["destination"].startswith("https://")
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


def test_telemetry_opt_in_changed():
    event = build_non_action_event("telemetry_opt_in_changed", {
        "previous_state": "opted_out",
        "new_state": "opted_in",
    })
    assert event["event_type"] == "telemetry_opt_in_changed"
    assert event["previous_state"] == "opted_out"
    assert event["new_state"] == "opted_in"
    ok, err = verify_non_action_event_hash(event)
    assert ok, err


# ---------------------------------------------------------------------------
# Integrity monitor data paths
# ---------------------------------------------------------------------------

def test_integrity_monitor_data_paths(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    from integrity_monitor import IntegrityMonitor

    chain_path = tmp_path / "chain.jsonl"
    chain_path.write_text("")
    telemetry_dir = tmp_path / "LOGS" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    summary = telemetry_dir / "summary.json"
    summary.write_text('{"test": true}')

    monitor = IntegrityMonitor(
        chain_path,
        data_paths=[summary],
    )
    h = monitor.current_data_hash()
    assert h is not None
    assert h.startswith("sha256:")


def test_integrity_monitor_data_hash_in_startup(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    from integrity_monitor import IntegrityMonitor

    chain_path = tmp_path / "chain.jsonl"
    chain_path.write_text("")
    telemetry_dir = tmp_path / "LOGS" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    summary = telemetry_dir / "summary.json"
    summary.write_text('{"transmissions": []}')

    # Create policy file
    policy = tmp_path / "policy-rules.json"
    policy.write_text('{"rules": []}')

    # Create code paths
    code = tmp_path / "server.py"
    code.write_text("# proxy")

    monitor = IntegrityMonitor(
        chain_path,
        policy_path=policy,
        code_paths=[code],
        data_paths=[summary],
    )
    hashes = monitor.startup_hashes()
    assert "current_data_hash" in hashes
    assert hashes["current_data_hash"].startswith("sha256:")
    assert str(summary) in hashes["data_paths"]


def test_integrity_monitor_data_hash_none_when_missing(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    from integrity_monitor import IntegrityMonitor

    chain_path = tmp_path / "chain.jsonl"
    chain_path.write_text("")
    missing = tmp_path / "nonexistent.json"

    monitor = IntegrityMonitor(
        chain_path,
        data_paths=[missing],
    )
    h = monitor.current_data_hash()
    assert h is None
