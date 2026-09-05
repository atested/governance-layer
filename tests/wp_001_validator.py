#!/usr/bin/env python3
"""Independent observable scenarios for WP-001's six validators."""

from __future__ import annotations

import asyncio
import http.client
import json
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


REPO = Path(__file__).resolve().parents[1]
for location in (REPO, REPO / "scripts", REPO / "dashboard"):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from governance_foundation import (  # noqa: E402
    MATURITY_TIERS,
    GovernedSessionStore,
    SESSION_ROUTE,
    maturity_tier_catalog,
)
from policy_eval_v2 import load_policy_rules  # noqa: E402
from proxy.boundary import govern_provider_response  # noqa: E402
from proxy.providers.openai import OpenAIProvider  # noqa: E402
from proxy.server import ChainRecorder, GovernanceProxy, mediate_decision  # noqa: E402
from readout import _normalize_activity_entry  # noqa: E402


def _response(*calls: tuple[str, str, dict]) -> dict:
    tool_calls = [
        {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)},
        }
        for call_id, name, arguments in calls
    ]
    return {
        "id": "response-wp-001",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
    }


def _policy() -> dict:
    policy = deepcopy(load_policy_rules())
    policy["base_dirs"] = [str(REPO)]
    policy["maturity_tier"] = "personal"
    return policy


def _decider(policy: dict):
    return lambda call: mediate_decision(call.tool_name, call.args, policy=policy)


class TransportBoundaryCoverageValidator(unittest.TestCase):
    def test_zero_one_and_multiple_calls_are_inspected_before_release(self):
        provider = OpenAIProvider()
        fixtures = [
            _response(),
            _response(("call-1", "Read", {"file_path": str(REPO / "README.md")})),
            _response(
                ("call-1", "Read", {"file_path": str(REPO / "README.md")}),
                ("call-2", "Read", {"file_path": "/etc/shadow"}),
            ),
        ]
        for expected_count, fixture in enumerate(fixtures):
            governed = govern_provider_response(provider, fixture, _decider(_policy()))
            inspections = [o for o in governed.observations if o["event"] == "call_inspected"]
            classifications = [o for o in governed.observations if o["event"] == "call_classified"]
            release_index = next(i for i, o in enumerate(governed.observations) if o["event"] == "response_released")
            self.assertEqual(len(inspections), expected_count)
            self.assertEqual(len(classifications), expected_count)
            self.assertEqual(len({o["call_id"] for o in inspections}), expected_count)
            self.assertTrue(all(i < release_index for i, o in enumerate(governed.observations) if o["event"] in {"call_inspected", "call_classified"}))
        self.assertEqual(fixtures[0], govern_provider_response(provider, fixtures[0], _decider(_policy())).body)


class DeterministicPolicyClassificationValidator(unittest.TestCase):
    def test_identical_inputs_classify_identically_before_release(self):
        policy = _policy()
        call = ("call-1", "Read", {"file_path": str(REPO / "README.md")})
        first = govern_provider_response(OpenAIProvider(), _response(call), _decider(policy))
        second = govern_provider_response(OpenAIProvider(), _response(call), _decider(policy))
        first_record = first.decisions[0][1]
        second_record = second.decisions[0][1]
        self.assertEqual(first_record["classification"], second_record["classification"])
        self.assertEqual(first_record["policy_decision"], second_record["policy_decision"])
        self.assertEqual(first_record["matched_rule"], second_record["matched_rule"])
        events = [item["event"] for item in first.observations]
        self.assertLess(events.index("call_classified"), events.index("response_released"))


class PolicyOutcomeEnforcementValidator(unittest.TestCase):
    def test_allow_payload_is_exact_and_deny_has_no_executable_original(self):
        provider = OpenAIProvider()
        allowed = _response(("allow-1", "Read", {"file_path": str(REPO / "README.md")}))
        governed_allow = govern_provider_response(provider, allowed, _decider(_policy()))
        self.assertEqual(governed_allow.decisions[0][1]["policy_decision"], "ALLOW")
        self.assertEqual(governed_allow.body, allowed)

        denied = _response(("deny-1", "Read", {"file_path": "/etc/shadow"}))
        governed_deny = govern_provider_response(provider, denied, _decider(_policy()))
        self.assertEqual(governed_deny.decisions[0][1]["policy_decision"], "DENY")
        encoded = json.dumps(governed_deny.body)
        self.assertNotIn('"type": "function"', encoded)
        self.assertNotIn('"id": "deny-1"', encoded)
        self.assertIn("Governance", encoded)


class GovernedSessionRoutingValidator(unittest.TestCase):
    def test_only_scoped_proxy_observed_session_becomes_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = GovernedSessionStore(Path(temporary))
            with self.assertRaises(ValueError):
                store.configure({}, proxy_url="http://127.0.0.1:8080", maturity_tier="personal")
            session = store.configure(
                {"working_directory": str(REPO)},
                proxy_url="http://127.0.0.1:8080",
                maturity_tier="crew",
            )
            self.assertFalse(session["governed_ready"])
            bypass = store.observe_route(session["session_id"], route="direct_provider")
            self.assertFalse(bypass["governed_ready"])
            observed = store.observe_route(
                session["session_id"], route=SESSION_ROUTE, provider="openai", path="/v1/responses"
            )
            self.assertTrue(observed["governed_ready"])
            withdrawn = store.observe_route(session["session_id"], route="alternate_proxy")
            self.assertFalse(withdrawn["governed_ready"])


class FourTierConsistencyValidator(unittest.TestCase):
    def test_policy_dashboard_and_evidence_share_four_ordered_identities(self):
        self.assertEqual(MATURITY_TIERS, ("personal", "crew", "team", "institution"))
        catalog = maturity_tier_catalog()
        self.assertEqual([item["id"] for item in catalog], list(MATURITY_TIERS))
        self.assertEqual([item["order"] for item in catalog], [1, 2, 3, 4])

        policy = _policy()
        policy["maturity_tier"] = "team"
        decision = mediate_decision(
            "Read", {"file_path": str(REPO / "README.md")}, policy=policy
        )
        activity = _normalize_activity_entry(decision, 1)
        with tempfile.TemporaryDirectory() as temporary:
            dashboard_state = GovernedSessionStore(Path(temporary)).configure(
                {"working_directory": str(REPO)},
                proxy_url="http://127.0.0.1:8080",
                maturity_tier="team",
            )
        self.assertEqual(decision["maturity_tier"], "team")
        self.assertEqual(activity["detail"]["maturity_tier"], "team")
        self.assertEqual(activity["evidence"]["maturity_tier"], "team")
        self.assertEqual(dashboard_state["maturity_tier"], "team")
        bad_policy = _policy()
        bad_policy["maturity_tier"] = "personal_plus"
        with self.assertRaises(ValueError):
            mediate_decision("Read", {"file_path": str(REPO / "README.md")}, policy=bad_policy)

    def test_session_tier_flows_through_proxy_policy_dashboard_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            store = GovernedSessionStore(runtime)
            session = store.configure(
                {"working_directory": str(REPO)},
                proxy_url="http://127.0.0.1:8080",
                maturity_tier="institution",
            )
            chain_path = runtime / "decision-chain.jsonl"
            proxy = GovernanceProxy(
                policy=_policy(),
                chain_recorder=ChainRecorder(chain_path),
                chain_path=chain_path,
                session_store=store,
            )
            upstream = MagicMock()
            upstream.status_code = 200
            upstream.headers = {"content-type": "application/json"}
            upstream.content = json.dumps(_response(
                ("call-1", "Read", {"file_path": str(REPO / "README.md")})
            )).encode()
            client = AsyncMock()
            client.request = AsyncMock(return_value=upstream)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            with patch("proxy.server.httpx.AsyncClient", return_value=client):
                status, _, _ = asyncio.run(proxy.handle_request(
                    "POST",
                    "/v1/chat/completions",
                    {"content-type": "application/json", "x-atested-session-id": session["session_id"]},
                    json.dumps({"messages": []}).encode(),
                    provider=OpenAIProvider(),
                ))
            self.assertEqual(status, 200)
            decision = json.loads(chain_path.read_text(encoding="utf-8").splitlines()[0])
            activity = _normalize_activity_entry(decision, 1)
            dashboard_state = store.status(session["session_id"])
            self.assertTrue(dashboard_state["governed_ready"])
            self.assertEqual(decision["maturity_tier"], "institution")
            self.assertEqual(activity["detail"]["maturity_tier"], "institution")
            self.assertEqual(activity["evidence"]["maturity_tier"], "institution")
            self.assertEqual(dashboard_state["maturity_tier"], "institution")


class DashboardUrlAccessValidator(unittest.TestCase):
    def test_authenticated_browser_reaches_dashboard_and_unauthenticated_is_withheld(self):
        import dashboard.server as dashboard_server

        with tempfile.TemporaryDirectory() as temporary:
            old_runtime = dashboard_server.RUNTIME
            old_token = dashboard_server._DASHBOARD_TOKEN
            old_port = dashboard_server._DASHBOARD_PORT
            dashboard_server.RUNTIME = Path(temporary)
            dashboard_server._DASHBOARD_TOKEN = "wp001-browser-token"
            server = dashboard_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), dashboard_server.DashboardHandler
            )
            dashboard_server._DASHBOARD_PORT = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                connection.request("GET", "/", headers={"User-Agent": "Mozilla/5.0 desktop"})
                unauthenticated = connection.getresponse()
                unauthenticated.read()
                self.assertEqual(unauthenticated.status, 401)

                connection.request("POST", "/api/governed-session/configure", body=b"{}", headers={"Content-Type": "application/json", "Content-Length": "2"})
                unauthenticated_action = connection.getresponse()
                unauthenticated_action.read()
                self.assertEqual(unauthenticated_action.status, 401)
                self.assertFalse((Path(temporary) / "governed-sessions.json").exists())

                connection.request("GET", "/auth?token=wp001-browser-token")
                authenticated = connection.getresponse()
                authenticated.read()
                self.assertEqual(authenticated.status, 303)
                cookie = authenticated.getheader("Set-Cookie").split(";", 1)[0]

                connection.request("GET", "/", headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 desktop"})
                dashboard = connection.getresponse()
                html = dashboard.read().decode("utf-8")
                self.assertEqual(dashboard.status, 200)
                self.assertIn("Atested Dashboard", html)

                connection.request("GET", "/api/governed-session", headers={"Cookie": cookie})
                operator_data = connection.getresponse()
                payload = json.loads(operator_data.read())
                self.assertEqual(operator_data.status, 200)
                self.assertEqual([item["id"] for item in payload["maturity_tiers"]], list(MATURITY_TIERS))
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                dashboard_server.RUNTIME = old_runtime
                dashboard_server._DASHBOARD_TOKEN = old_token
                dashboard_server._DASHBOARD_PORT = old_port


if __name__ == "__main__":
    unittest.main(verbosity=2)
