#!/usr/bin/env python3
"""Independent observable scenarios for WP-006's two validators."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from local_continuity import LOCAL_CAPABILITIES, LocalGovernanceRuntime  # noqa: E402


def _key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def _classification(target: str) -> dict:
    return {
        "original_tool": "FS_READ",
        "operation_description": f"Read {target}",
        "action_type": "read",
        "targets": [target],
        "scope": "local",
        "confidence_tier": 1,
        "evidence": {},
    }


class LocalFirstContinuityValidator(unittest.TestCase):
    def test_local_functions_continue_and_provider_is_truthfully_unavailable(self):
        provider_calls = []
        with tempfile.TemporaryDirectory() as temp:
            runtime = LocalGovernanceRuntime(
                Path(temp) / "decision-chain.jsonl",
                hosted_reachable=False,
                provider_operation=lambda: provider_calls.append("called"),
                signing_key=_key(),
            )
            status = runtime.capability_status()
            self.assertEqual(set(status["local_functions"]), set(LOCAL_CAPABILITIES))
            self.assertTrue(all(item["status"] == "available" for item in status["local_functions"].values()))
            self.assertEqual(status["provider_interaction"]["status"], "unavailable")
            self.assertFalse(status["provider_interaction"]["completed"])

            policy = {
                "maturity_tier": "personal",
                "base_dirs": [temp],
                "rules": [{
                    "id": "local-read", "match": {"action_type": ["read"]},
                    "decision": "ALLOW", "reason": "local read",
                }],
                "default_decision": "DENY",
            }
            first = runtime.evaluate_policy(
                _classification(str(Path(temp) / "one.txt")), policy,
                user_identity="operator-local",
            )
            second = runtime.evaluate_policy(
                _classification(str(Path(temp) / "two.txt")), policy,
                user_identity="operator-local",
            )
            self.assertEqual(first["policy_decision"], "ALLOW")
            runtime.record_decision(first, subject_id="operator-local")
            runtime.record_decision(second, subject_id="operator-local")
            self.assertEqual(len(runtime.records()), 2)
            self.assertEqual(len(runtime.dashboard_review(decision="ALLOW")), 2)

            scope = {"record_ids": [runtime.records()[0]["record_id"]]}
            artifact = runtime.generate_report(
                scope=scope, issuer="operator-local", created_at="2026-09-04T12:00:00Z"
            )
            self.assertTrue(runtime.verify_evidence(artifact, expected_scope=scope)["valid"])
            unavailable = runtime.provider_interaction()
            self.assertEqual(unavailable["status"], "unavailable")
            self.assertFalse(unavailable["completed"])
            self.assertEqual(provider_calls, [])


class ScopedEvidencePackageValidator(unittest.TestCase):
    def test_package_is_scope_limited_independently_verifiable_and_mutation_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = LocalGovernanceRuntime(Path(temp) / "chain.jsonl", signing_key=_key())
            for identity, decision in (("alice", "ALLOW"), ("bob", "DENY"), ("alice", "DENY")):
                runtime.record_decision(
                    {"policy_decision": decision, "timestamp_utc": "2026-09-04T12:00:00Z"},
                    subject_id=identity,
                )
            scope = {"subject_ids": ["alice"], "decisions": ["DENY"]}
            artifact = runtime.generate_report(
                scope=scope, issuer="audit-export", created_at="2026-09-04T12:05:00Z"
            )
            parsed = json.loads(artifact)
            selected = parsed["content"]["records"]
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]["subject_id"], "alice")
            self.assertEqual(selected[0]["payload"]["policy_decision"], "DENY")
            self.assertNotIn("bob", artifact.decode("utf-8"))
            result = runtime.verify_evidence(artifact, expected_scope=scope)
            self.assertTrue(result["valid"])
            self.assertTrue(result["integrity_valid"])
            self.assertTrue(result["authentication_valid"])
            self.assertEqual(result["authentication_basis"], "Ed25519")

            mutated = artifact.replace(b'"policy_decision":"DENY"', b'"policy_decision":"D3NY"', 1)
            self.assertNotEqual(mutated, artifact)
            mutation_result = runtime.verify_evidence(mutated, expected_scope=scope)
            self.assertFalse(mutation_result["valid"])
            self.assertFalse(mutation_result["integrity_valid"])

    def test_empty_or_unknown_scope_cannot_expand_to_all_records(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = LocalGovernanceRuntime(Path(temp) / "chain.jsonl", signing_key=_key())
            runtime.record_decision({"policy_decision": "ALLOW"}, subject_id="alice")
            for unsafe_scope in ({}, {"subject": ["alice"]}):
                with self.subTest(scope=unsafe_scope), self.assertRaises(ValueError):
                    runtime.generate_report(scope=unsafe_scope, issuer="audit-export")


if __name__ == "__main__":
    unittest.main(verbosity=2)
