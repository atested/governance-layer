"""Tests for event model type registration completeness.

Verifies that all event types used in dashboard/server.py and MCP server
are registered in NON_ACTION_EVENT_TYPES, so build_non_action_event does
not raise ValueError at runtime.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.event_model import build_non_action_event, NON_ACTION_EVENT_TYPES


def _payload_for(event_type):
    common_hash = "sha256:" + "a" * 64
    payloads = {
        "remote_chain_import": {
            "source_machine_id": "remote-1",
            "source_machine_key_id": "ed25519:key",
            "segment_id": common_hash,
            "segment_kind": "current_chain",
            "stored_segment_sha256": common_hash,
            "remote_first_record_hash": common_hash,
            "remote_last_record_hash": common_hash,
            "remote_record_count": 1,
            "import_sequence": 1,
            "sync_session_id": "sync-1",
            "primary_import_timestamp_utc": "2026-05-09T00:00:00Z",
            "verification_result": "PASS",
        },
        "machine_added": {
            "subject_machine_id": "remote-1",
            "subject_machine_role": "remote",
            "public_key_fingerprint": "ed25519:key",
            "operator_confirmation_event_id": "confirm-1",
            "license_status": "active",
            "sync_authorized": True,
            "registry_hash_after": common_hash,
        },
        "machine_removed": {
            "subject_machine_id": "remote-1",
            "license_status": "removed",
            "sync_authorized": False,
            "registry_hash_after": common_hash,
        },
        "machine_role_changed": {
            "subject_machine_id": "remote-1",
            "from_role": "remote",
            "to_role": "primary",
            "registry_hash_after": common_hash,
        },
        "machine_key_rotated": {
            "subject_machine_id": "remote-1",
            "old_public_key_fingerprint": "ed25519:old",
            "new_public_key_fingerprint": "ed25519:new",
            "registry_hash_after": common_hash,
        },
        "machine_license_status_changed": {
            "subject_machine_id": "remote-1",
            "from_license_status": "active",
            "to_license_status": "removed",
            "sync_authorized": False,
            "registry_hash_after": common_hash,
        },
        "version_check_performed": {
            "current_version": "1.0.0",
            "latest_version": "1.0.1",
            "update_available": True,
        },
        "trouble_report_submitted": {
            "destination": "https://license.atested.com/api/trouble-report",
            "payload_hash": common_hash,
            "payload_size": 123,
        },
        "telemetry_submitted": {
            "destination": "https://license.atested.com/api/telemetry",
            "payload_hash": common_hash,
            "payload_size": 123,
        },
        "telemetry_opt_in_changed": {"previous_state": "opted_out", "new_state": "opted_in"},
        "license_validation_attempted": {"result": "success", "endpoint": "/api/config/verify-license"},
        "failed_authentication_attempt": {"endpoint": "/api/export", "failure_reason": "bad_key"},
        "dashboard_config_unlocked": {"operator_label": "Operator", "tier": "crew"},
        "notification_received": {"notification_id": "n1", "notification_type": "version_update"},
        "registry_config_change": {"new_registry_hash": common_hash, "tools_count": 1, "licensed": True},
        "report_exported": {"report_name": "activity", "format": "json", "record_count": 1},
        "chain_export_created": {"record_count": 1},
        "encrypted_evidence_package_created": {
            "package_id": "ep_test",
            "operator_identity": "operator",
            "record_count": 1,
            "password_recorded": False,
        },
        "governance_integrity_error": {
            "tool_name": "bash",
            "condition_source": "qa_chain_staleness",
            "condition_detail": "latest QA snapshot sequence has not advanced",
            "action_taken": "integrity_error_returned",
        },
    }
    return payloads.get(event_type, {"test": True})


# Event types that were missing and caused runtime crashes (D-076 Fix 2)
_PREVIOUSLY_MISSING = [
    "institution_inquiry_submitted",
    "research_program_opted_in",
    "research_program_opt_in_changed",
    "communications_request_submitted",
    "terms_acknowledged",
]


class TestEventTypeRegistration:
    @pytest.mark.parametrize("event_type", _PREVIOUSLY_MISSING)
    def test_previously_missing_types_registered(self, event_type):
        """Each formerly-missing event type must be in the frozenset."""
        assert event_type in NON_ACTION_EVENT_TYPES

    @pytest.mark.parametrize("event_type", _PREVIOUSLY_MISSING)
    def test_previously_missing_types_buildable(self, event_type):
        """build_non_action_event must not raise for these types."""
        event = build_non_action_event(event_type, {"test": True})
        assert event["event_type"] == event_type
        assert event["record_hash"] is not None

    def test_unknown_type_still_raises(self):
        """Unregistered types must still raise ValueError."""
        with pytest.raises(ValueError, match="unknown non-action event_type"):
            build_non_action_event("totally_bogus_event", {})

    def test_all_registered_types_buildable(self):
        """Every type in the frozenset must be buildable without error."""
        for event_type in sorted(NON_ACTION_EVENT_TYPES):
            event = build_non_action_event(event_type, _payload_for(event_type))
            assert event["event_type"] == event_type
            assert "machine_id" in event
            assert event["machine_role"] in ("primary", "remote")
            assert "event_timestamp_utc" in event

    @pytest.mark.parametrize("event_type", [
        "remote_chain_import",
        "machine_added",
        "machine_removed",
        "machine_role_changed",
        "machine_key_rotated",
        "machine_license_status_changed",
        "version_check_performed",
    ])
    def test_security_sensitive_events_reject_empty_payload(self, event_type):
        from scripts.event_model import validate_non_action_event
        event = build_non_action_event(event_type, {})
        ok, err = validate_non_action_event(event)
        assert not ok
        assert err
