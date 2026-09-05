#!/usr/bin/env python3
"""Independent observable scenarios for WP-003's five validators."""

from __future__ import annotations

import json
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
for location in (REPO, REPO / "scripts"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from approval_store import ApprovalStore, explicit_operator_action_fields  # noqa: E402
from policy_eval_v2 import load_policy_rules  # noqa: E402
from proxy.boundary import govern_provider_response  # noqa: E402
from proxy.providers.openai import OpenAIProvider  # noqa: E402
from proxy.server import mediate_decision  # noqa: E402


OPERATOR = "operator-alice"
OTHER_OPERATOR = "operator-bob"
FAMILY = "mcp_tools_v1"
CONTEXT = "wp003-host"
POLICY_VERSION = "wp003-policy-v1"
OPAQUE_TOOL = "Bash"
OPAQUE_ARGS = {"command": "python -c 'print(42)'"}
GOVERNANCE_ENV = {
    "GOV_GOVERNED_FAMILY": FAMILY,
    "GOV_DEPLOYMENT_CONTEXT": CONTEXT,
    "GOV_POLICY_VERSION": POLICY_VERSION,
}


def _policy() -> dict:
    policy = deepcopy(load_policy_rules())
    policy["base_dirs"] = [str(REPO)]
    return policy


def _decision(
    *,
    args: dict | None = None,
    store: ApprovalStore | None = None,
    operator: str = OPERATOR,
    developer_mode: bool = False,
) -> dict:
    with patch.dict(os.environ, GOVERNANCE_ENV, clear=False), patch(
        "proxy.server.developer_mode_active", return_value=developer_mode,
    ):
        return mediate_decision(
            OPAQUE_TOOL,
            args or OPAQUE_ARGS,
            policy=_policy(),
            approval_store=store,
            user_identity=operator,
            session_id="governed-session",
        )


def _explicit_approval(
    operation_identity: str,
    *,
    operator: str = OPERATOR,
    family: str = FAMILY,
    context: str = CONTEXT,
    policy_version: str = POLICY_VERSION,
    **overrides,
) -> dict:
    event = {
        "event_type": "opaque_artifact_approval",
        "event_id": "approval-wp003",
        "artifact_identity": operation_identity,
        "approving_operator": operator,
        "governed_family": family,
        "deployment_context": context,
        "policy_version": policy_version,
        **explicit_operator_action_fields(operator, channel="authenticated_dashboard"),
    }
    event.update(overrides)
    return event


def _store_for(operation_identity: str, **overrides) -> ApprovalStore:
    store = ApprovalStore()
    store.ingest_approval(_explicit_approval(operation_identity, **overrides))
    return store


def _openai_response() -> dict:
    return {
        "id": "response-wp003",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-wp003",
                    "type": "function",
                    "function": {"name": OPAQUE_TOOL, "arguments": json.dumps(OPAQUE_ARGS)},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


class Tier3OpaqueApprovalGateValidator(unittest.TestCase):
    def test_tier3_call_is_withheld_until_matching_approval_exists(self):
        denied = _decision()
        self.assertEqual(denied["classification"]["confidence_tier"], 3)
        self.assertEqual(denied["policy_decision"], "DENY")
        self.assertTrue(denied["operation_identity"].startswith("sha256:"))

        with patch.dict(os.environ, GOVERNANCE_ENV, clear=False), patch(
            "proxy.server.developer_mode_active", return_value=False,
        ):
            governed = govern_provider_response(
                OpenAIProvider(),
                _openai_response(),
                lambda call: mediate_decision(
                    call.tool_name,
                    call.args,
                    policy=_policy(),
                    user_identity=OPERATOR,
                ),
            )
        self.assertEqual(governed.decisions[0][1]["policy_decision"], "DENY")
        released = json.dumps(governed.body)
        self.assertNotIn('"type": "function"', released)
        self.assertNotIn('"id": "call-wp003"', released)

        approved = _decision(store=_store_for(denied["operation_identity"]))
        self.assertEqual(approved["policy_decision"], "ALLOW")
        self.assertEqual(approved["decision_basis"], "explicit_operator_approval")


class ExplicitHumanApprovalOnlyValidator(unittest.TestCase):
    def test_non_operator_origins_never_create_consumable_approval(self):
        operation_identity = _decision()["operation_identity"]
        invalid_provenance = (
            {"authorization_origin": "automatic"},
            {"authorization_origin": "scheduled", "scheduled_for": "2026-09-05T00:00:00Z"},
            {"authorization_origin": "policy_rule", "policy_rule_origin": "auto-allow"},
            {"authorization_origin": "delegated", "delegated_by": "operator-alice"},
            {"explicit_operator_action": False},
            {"authenticated_operator_id": ""},
            {"operator_action_channel": "background_worker"},
        )
        for provenance in invalid_provenance:
            with self.subTest(provenance=provenance):
                store = _store_for(operation_identity, **provenance)
                self.assertEqual(_decision(store=store)["policy_decision"], "DENY")


class ApprovalScopeLifetimeValidator(unittest.TestCase):
    def test_operation_and_every_operator_context_dimension_must_remain_unchanged(self):
        original = _decision()
        store = _store_for(original["operation_identity"])
        self.assertEqual(_decision(store=store)["policy_decision"], "ALLOW")

        changed_operation = _decision(
            args={"command": "python -c 'print(43)'"}, store=store,
        )
        self.assertEqual(changed_operation["policy_decision"], "DENY")
        self.assertNotEqual(changed_operation["operation_identity"], original["operation_identity"])
        self.assertEqual(_decision(store=store, operator=OTHER_OPERATOR)["policy_decision"], "DENY")

        for env_change in (
            {"GOV_GOVERNED_FAMILY": "other-family"},
            {"GOV_DEPLOYMENT_CONTEXT": "other-host"},
            {"GOV_POLICY_VERSION": "wp003-policy-v2"},
        ):
            with self.subTest(env_change=env_change), patch.dict(
                os.environ, {**GOVERNANCE_ENV, **env_change}, clear=False,
            ), patch("proxy.server.developer_mode_active", return_value=False):
                record = mediate_decision(
                    OPAQUE_TOOL,
                    OPAQUE_ARGS,
                    policy=_policy(),
                    approval_store=store,
                    user_identity=OPERATOR,
                )
                self.assertEqual(record["policy_decision"], "DENY")


class ApprovalRevocationValidator(unittest.TestCase):
    def test_acknowledged_revocation_is_ineligible_for_all_later_decisions(self):
        operation_identity = _decision()["operation_identity"]
        store = _store_for(operation_identity)
        self.assertEqual(_decision(store=store)["policy_decision"], "ALLOW")
        store.ingest_revocation({
            "event_type": "opaque_artifact_revocation",
            "event_id": "revocation-wp003",
            "artifact_identity": operation_identity,
            "revoking_operator": OPERATOR,
            "governed_family": FAMILY,
            "deployment_context": CONTEXT,
            "policy_version": POLICY_VERSION,
            **explicit_operator_action_fields(OPERATOR, channel="authenticated_dashboard"),
        })
        for developer_mode in (False, True):
            with self.subTest(developer_mode=developer_mode):
                self.assertEqual(
                    _decision(store=store, developer_mode=developer_mode)["policy_decision"],
                    "DENY",
                )


class NoDeveloperDenyBypassValidator(unittest.TestCase):
    def test_production_and_developer_modes_require_the_same_approval(self):
        operation_identity = _decision()["operation_identity"]
        store = _store_for(operation_identity)
        for developer_mode in (False, True):
            with self.subTest(mode=developer_mode, approval=False):
                denied = _decision(developer_mode=developer_mode)
                self.assertEqual(denied["policy_decision"], "DENY")
            with self.subTest(mode=developer_mode, approval=True):
                allowed = _decision(store=store, developer_mode=developer_mode)
                self.assertEqual(allowed["policy_decision"], "ALLOW")
                self.assertEqual(allowed["approval_operator_id"], OPERATOR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
