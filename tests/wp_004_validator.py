#!/usr/bin/env python3
"""Independent observable scenarios for WP-004's six validators."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from production_safety import (  # noqa: E402
    LOCAL_DEVELOPMENT,
    PRODUCTION,
    ProductionSafetyBoundary,
    RuntimeSafetyConfig,
    StartupSafetyError,
    validate_startup,
)


class ProductionSigningRequiredValidator(unittest.TestCase):
    def test_production_never_becomes_ready_without_usable_signing(self):
        config = RuntimeSafetyConfig(PRODUCTION, capacity=2)
        with self.assertRaisesRegex(StartupSafetyError, "usable.*signing"):
            ProductionSafetyBoundary(config, signing_usable=False, effective_uid=501)

        boundary = ProductionSafetyBoundary(config, signing_usable=True, effective_uid=501)
        self.assertTrue(boundary.health()["ready"])
        boundary.set_dependency("signing", False, "signer failed a post-startup probe")
        health = boundary.health()
        self.assertFalse(health["ready"])
        self.assertEqual(health["degraded_conditions"][0]["failure_class"], "signing")
        self.assertIsNone(boundary.try_admit())


class UnsignedLocalDevelopmentBoundaryValidator(unittest.TestCase):
    def test_unsigned_startup_requires_explicit_local_development_context(self):
        local = RuntimeSafetyConfig.from_environment({
            "ATESTED_RUNTIME_CONTEXT": LOCAL_DEVELOPMENT,
            "ATESTED_GOVERNANCE_CAPACITY": "1",
        })
        boundary = ProductionSafetyBoundary(local, signing_usable=False, effective_uid=0)
        self.assertTrue(boundary.health()["ready"])
        self.assertEqual(boundary.health()["runtime_context"], LOCAL_DEVELOPMENT)

        for environment in ({}, {"ATESTED_RUNTIME_CONTEXT": ""}, {"ATESTED_RUNTIME_CONTEXT": "developer"}):
            with self.subTest(environment=environment), self.assertRaises(StartupSafetyError):
                RuntimeSafetyConfig.from_environment(environment)


class NonRootProductionRuntimeValidator(unittest.TestCase):
    def test_production_identity_is_non_root_in_validation_and_image(self):
        config = RuntimeSafetyConfig(PRODUCTION)
        validate_startup(config, signing_usable=True, effective_uid=501)
        with self.assertRaisesRegex(StartupSafetyError, "must not run as root"):
            validate_startup(config, signing_usable=True, effective_uid=0)

        dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER atested", dockerfile)
        self.assertNotIn("GOV_SIGNING_DEV_MODE=1", dockerfile)


class GovernanceHealthStatusValidator(unittest.TestCase):
    def test_liveness_remains_distinct_while_each_dependency_withdraws_readiness(self):
        for dependency in ("policy", "signing", "decision_record", "approval"):
            with self.subTest(dependency=dependency):
                boundary = ProductionSafetyBoundary(
                    RuntimeSafetyConfig(PRODUCTION), signing_usable=True, effective_uid=501,
                )
                boundary.set_dependency(dependency, False, f"{dependency} probe unavailable")
                health = boundary.health()
                self.assertTrue(health["live"])
                self.assertFalse(health["ready"])
                self.assertFalse(health["dependencies"][dependency]["available"])
                self.assertEqual(health["degraded_conditions"][0]["dependency"], dependency)

        source = (REPO / "proxy" / "server.py").read_text(encoding="utf-8")
        self.assertIn('{"/livez", "/readyz"}', source)
        self.assertIn("status = 200 if healthy else 503", source)


class GovernanceOverloadSafetyValidator(unittest.TestCase):
    def test_excess_demand_is_bounded_and_explicitly_refused(self):
        boundary = ProductionSafetyBoundary(
            RuntimeSafetyConfig(PRODUCTION, capacity=2), signing_usable=True, effective_uid=501,
        )
        first = boundary.try_admit()
        second = boundary.try_admit()
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertIsNone(boundary.try_admit())

        refusal = boundary.current_refusal()
        self.assertFalse(refusal["released"])
        self.assertFalse(refusal["governed_success"])
        self.assertEqual(refusal["reason_code"], "GOVERNANCE_CAPACITY_UNAVAILABLE")
        self.assertEqual(boundary.health()["capacity"]["in_flight"], 2)

        first.release()
        replacement = boundary.try_admit()
        self.assertIsNotNone(replacement)
        replacement.release()
        second.release()
        self.assertEqual(boundary.health()["capacity"]["in_flight"], 0)


class UnsafeConditionRefusalValidator(unittest.TestCase):
    def test_every_named_failure_is_visible_and_never_represented_as_success(self):
        boundary = ProductionSafetyBoundary(
            RuntimeSafetyConfig(PRODUCTION), signing_usable=True, effective_uid=501,
        )
        for failure_class in ("integrity", "signing", "authorization", "capacity"):
            with self.subTest(failure_class=failure_class):
                refusal = boundary.refuse(failure_class, "validator", f"{failure_class} unavailable")
                self.assertEqual(refusal["policy_decision"], "DENY")
                self.assertFalse(refusal["released"])
                self.assertFalse(refusal["governed_success"])
                self.assertEqual(
                    refusal["degraded_condition"]["failure_class"], failure_class,
                )
                self.assertEqual(
                    refusal["degraded_condition"]["action"], "affected_operation_refused",
                )
                json.dumps(refusal, sort_keys=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
