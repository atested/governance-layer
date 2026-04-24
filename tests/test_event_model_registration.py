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
            event = build_non_action_event(event_type, {"test": True})
            assert event["event_type"] == event_type
