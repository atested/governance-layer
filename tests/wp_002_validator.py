#!/usr/bin/env python3
"""Independent observable scenarios for WP-002's four validators."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from decision_evidence import SignedGovernanceLedger, verify_signed_chain  # noqa: E402


class EvidenceScenario(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.chain = Path(self.temporary.name) / "governance-evidence.jsonl"
        self.key = Ed25519PrivateKey.generate()
        self.ledger = SignedGovernanceLedger(self.chain, self.key)

    def tearDown(self):
        self.temporary.cleanup()

    def policy_context(self):
        return {"policy_id": "baseline-v1", "rule_id": "WP002_TEST"}


class PreExecutionDecisionRecordValidator(EvidenceScenario):
    def test_allow_deny_and_approval_terminal_outcomes_have_one_prior_decision(self):
        allow = self.ledger.record_decision(
            "operation-allow", decision="ALLOW", policy_context=self.policy_context()
        )
        allow_terminal = self.ledger.record_terminal_outcome(allow)

        deny = self.ledger.record_decision(
            "operation-deny", decision="DENY", policy_context=self.policy_context(),
            reason_codes=["PATH_OUTSIDE_SCOPE"],
        )
        deny_terminal = self.ledger.record_terminal_outcome(deny)

        approval = self.ledger.record_operator_action(
            "operation-approved", authenticated_operator_id="operator-42", action="APPROVE"
        )
        approved = self.ledger.record_decision(
            "operation-approved", decision="ALLOW", policy_context=self.policy_context(),
            operator_action_record_id=approval["record_id"],
        )
        approved_terminal = self.ledger.record_terminal_outcome(approved)

        records = [json.loads(line) for line in self.chain.read_text().splitlines()]
        positions = {record["record_id"]: index for index, record in enumerate(records)}
        for decision, terminal in (
            (allow, allow_terminal), (deny, deny_terminal), (approved, approved_terminal),
        ):
            self.assertLess(positions[decision["record_id"]], positions[terminal["record_id"]])
            self.assertEqual(terminal["payload"]["decision_record_id"], decision["record_id"])
            self.assertEqual(terminal["payload"]["decision_record_hash"], decision["record_hash"])
        self.assertTrue(verify_signed_chain(self.chain, self.key.public_key())["valid"])


class SignedChainIntegrityValidator(EvidenceScenario):
    def _complete_chain(self):
        approval = self.ledger.record_operator_action(
            "operation-1", authenticated_operator_id="operator-1", action="APPROVE"
        )
        decision = self.ledger.record_decision(
            "operation-1", decision="ALLOW", policy_context=self.policy_context(),
            operator_action_record_id=approval["record_id"],
        )
        self.ledger.record_terminal_outcome(decision)
        return self.ledger.checkpoint()

    def _copy(self, name):
        target = self.chain.with_name(name)
        shutil.copyfile(self.chain, target)
        return target

    def test_intact_altered_deleted_inserted_and_reordered_evidence(self):
        checkpoint = self._complete_chain()
        intact = verify_signed_chain(self.chain, self.key.public_key(), checkpoint=checkpoint)
        self.assertTrue(intact["valid"])

        altered = self._copy("altered.jsonl")
        altered.write_text(altered.read_text().replace("operator-1", "operator-x", 1))

        deleted = self._copy("deleted.jsonl")
        deleted_lines = deleted.read_text().splitlines()
        deleted.write_text("\n".join(deleted_lines[:-1]) + "\n")

        inserted = self._copy("inserted.jsonl")
        inserted_lines = inserted.read_text().splitlines()
        inserted.write_text("\n".join([inserted_lines[0], inserted_lines[0], *inserted_lines[1:]]) + "\n")

        reordered = self._copy("reordered.jsonl")
        reordered_lines = reordered.read_text().splitlines()
        reordered_lines[0], reordered_lines[1] = reordered_lines[1], reordered_lines[0]
        reordered.write_text("\n".join(reordered_lines) + "\n")

        for path in (altered, deleted, inserted, reordered):
            result = verify_signed_chain(path, self.key.public_key(), checkpoint=checkpoint)
            self.assertFalse(result["valid"], path.name)
            self.assertIsInstance(result["first_affected_boundary"], int)
            self.assertGreaterEqual(result["first_affected_boundary"], 1)


class OperatorActionAttributionValidator(EvidenceScenario):
    def test_approval_and_revocation_are_attributed_and_signed(self):
        approval = self.ledger.record_operator_action(
            "operation-1", authenticated_operator_id="operator-alice", action="APPROVE"
        )
        revocation = self.ledger.record_operator_action(
            "operation-1", authenticated_operator_id="operator-alice", action="REVOKE"
        )
        for record, action in ((approval, "APPROVE"), (revocation, "REVOKE")):
            self.assertEqual(record["operation_id"], "operation-1")
            self.assertEqual(record["payload"]["authenticated_operator_id"], "operator-alice")
            self.assertEqual(record["payload"]["action"], action)
            self.assertTrue(record["payload"]["decision_time"].endswith("Z"))
            self.assertTrue(record["signature"])
            self.assertTrue(record["signing_key_id"].startswith("ed25519:"))
        self.assertTrue(verify_signed_chain(self.chain, self.key.public_key())["valid"])


class DenialReasonCodeValidator(EvidenceScenario):
    def test_denial_result_and_decision_share_stable_reason_codes(self):
        decision = self.ledger.record_decision(
            "operation-deny", decision="DENY", policy_context=self.policy_context(),
            reason_codes=["PATH_OUTSIDE_SCOPE", "HIDDEN_PATH"],
        )
        terminal = self.ledger.record_terminal_outcome(decision)
        self.assertEqual(
            terminal["payload"]["reason_codes"],
            decision["payload"]["reason_codes"],
        )
        self.assertEqual(terminal["payload"]["outcome"], "REFUSED")
        self.assertTrue(verify_signed_chain(self.chain, self.key.public_key())["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

