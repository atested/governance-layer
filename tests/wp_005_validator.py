#!/usr/bin/env python3
"""Independent observable scenarios for WP-005's four validators."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from operator_review import WindowNavigator, decision_review, filter_activity, trace_summary  # noqa: E402


class OperatorDecisionReviewValidator(unittest.TestCase):
    def test_every_decision_state_has_truthful_execution_and_only_valid_actions(self):
        expected = {
            "ALLOW": (True, []), "DENY": (False, ["approve"]),
            "pending-approval": (False, ["approve"]), "approved": (False, ["revoke"]),
            "revoked": (False, ["approve"]),
        }
        for state, (executed, actions) in expected.items():
            with self.subTest(state=state):
                review = decision_review({"state": state, "operation_description": "Publish report", "reason_code": "POLICY", "evidence": {"record_id": "r1"}, "executed": True})
                self.assertEqual(review["executed"], executed)
                self.assertEqual(review["execution_status"], "executed" if executed else "not executed")
                self.assertEqual(review["available_actions"], actions)
                self.assertEqual(review["operation"], "Publish report")


class DashboardWindowModelValidator(unittest.TestCase):
    def test_parent_state_returns_and_persistent_signals_survive_two_levels(self):
        windows = WindowNavigator("operator-alice", "licensed", ("1 pending",))
        first = windows.open({"page": "activity", "filters": {"decision": "DENY"}})
        second = windows.open({"page": "record", "record_id": "rec-1"})
        self.assertEqual(second["depth"], 2)
        self.assertEqual(second["operator_identity"], "operator-alice")
        self.assertEqual(second["license_signal"], "licensed")
        self.assertEqual(second["notifications"], ["1 pending"])
        with self.assertRaises(ValueError):
            windows.open({"page": "third"})
        returned = windows.close()
        self.assertEqual(returned["view"], first["view"])
        self.assertEqual(returned["depth"], 1)


class DashboardInvestigationValidator(unittest.TestCase):
    def test_each_filter_selects_only_matching_source_records(self):
        records = [
            {"record_id": "a", "timestamp_utc": "2026-09-04T10:00:00Z", "confidence_tier": 1, "policy_decision": "ALLOW", "machine_id": "m1"},
            {"record_id": "b", "timestamp_utc": "2026-09-04T11:00:00Z", "confidence_tier": 2, "policy_decision": "DENY", "machine_id": "m2"},
            {"record_id": "c", "timestamp_utc": "2026-09-04T12:00:00Z", "confidence_tier": 2, "policy_decision": "DENY", "machine_id": "m1"},
        ]
        result = filter_activity(records, start_time="2026-09-04T10:30:00Z", end_time="2026-09-04T12:00:00Z", tier=2, decision="DENY", machine_id="m1")
        self.assertEqual([r["record_id"] for r in result], ["c"])
        self.assertEqual(records[2]["record_id"], "c")


class SummaryEvidenceTraceValidator(unittest.TestCase):
    def test_summary_resolves_supporting_chain_record_and_rejects_contradictions(self):
        record = {"record_id": "rec-1", "policy_decision": "DENY", "operation_description": "Publish report", "policy_context": "baseline-v2", "integrity_state": "verified"}
        summary = {"record_ids": ["rec-1"], "decision": "DENY", "operation": "Publish report", "policy_context": "baseline-v2", "integrity_state": "verified"}
        self.assertEqual(trace_summary(summary, [record]), [record])
        with self.assertRaises(ValueError):
            trace_summary({**summary, "decision": "ALLOW"}, [record])


if __name__ == "__main__":
    unittest.main(verbosity=2)
