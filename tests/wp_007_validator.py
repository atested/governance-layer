#!/usr/bin/env python3
"""Independent observable scenarios for WP-007's privacy validators."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from privacy_boundaries import (  # noqa: E402
    AiFeatureRequest,
    AuthenticatedAiSession,
    OptInAuthenticatedAiFeatureGate,
    PrivacyBoundaryError,
    aggregate_local_telemetry_summary,
    aggregate_telemetry_export,
    validate_aggregate_only_telemetry,
)


class AggregateOnlyTelemetryValidator(unittest.TestCase):
    def test_export_contains_only_fixed_count_dimensions(self):
        payload = aggregate_telemetry_export(
            {"lifetime": {"window_opens": {"dashboard": 2}, "ui_actions": {"approve": 1}}},
            {"governance_usage_data": {"total_operations": 4, "allow": 3, "deny": 1}, "trouble_submissions": {"submitted": 2}},
        )
        self.assertEqual(payload["ui_window_opens"], 2)
        self.assertEqual(payload["governance_total_operations"], 4)
        self.assertTrue(all(isinstance(value, int) and not isinstance(value, bool) for value in payload.values()))
        self.assertEqual(payload, validate_aggregate_only_telemetry(payload))

    def test_relay_summary_is_reduced_to_counts_without_copying_local_content(self):
        payload = aggregate_local_telemetry_summary({
            "lifetime": {
                "window_opens": {"dashboard": 2},
                "trouble_reports": {"submitted": 1},
                "untrusted_local_note": "must not leave the installation",
            },
        })
        self.assertEqual(payload["ui_window_opens"], 2)
        self.assertEqual(payload["trouble_reports"], 1)
        self.assertNotIn("untrusted_local_note", payload)

    def test_identifiable_content_free_text_and_non_counts_are_refused(self):
        for excluded in (
            {"operator_identity": "alice@example.test"},
            {"prompt": "summarize this client record"},
            {"ui_actions": "free text"},
            {"governance_allow": True},
        ):
            with self.subTest(excluded=excluded), self.assertRaises(PrivacyBoundaryError):
                validate_aggregate_only_telemetry(excluded)


class OptInAuthenticatedAiFeatureValidator(unittest.TestCase):
    def setUp(self):
        self.gate = OptInAuthenticatedAiFeatureGate()
        self.current = AuthenticatedAiSession(session_id="current-session", user_id="operator-alice")
        self.request = AiFeatureRequest(session_id="current-session", user_id="operator-alice", origin="interactive")
        self.calls: list[str] = []

    def _feature(self):
        self.calls.append("AI request")
        return "result"

    def test_only_explicit_opt_in_from_authenticated_current_user_session_can_invoke(self):
        self.assertEqual(self.gate.invoke(opted_in=True, current_session=self.current, request=self.request, feature=self._feature), "result")
        self.assertEqual(self.calls, ["AI request"])

    def test_opt_out_unauthenticated_different_session_automatic_and_delegated_origins_are_refused(self):
        cases = (
            (False, self.current, self.request),
            (True, None, self.request),
            (True, self.current, AiFeatureRequest("other-session", "operator-alice", "interactive")),
            (True, self.current, AiFeatureRequest("current-session", "operator-alice", "automatic")),
            (True, self.current, AiFeatureRequest("current-session", "operator-alice", "interactive", delegated=True)),
        )
        for opted_in, session, request in cases:
            with self.subTest(request=request), self.assertRaises(PrivacyBoundaryError):
                self.gate.invoke(opted_in=opted_in, current_session=session, request=request, feature=self._feature)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
