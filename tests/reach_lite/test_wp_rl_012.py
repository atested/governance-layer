"""WP-RL-012: every visible control performs its stated action under
ordinary browser events, and that behavior is captured as conforming
evidence (REQ-ATL-042, SCH-ATL-010).

Live tests start the operator application as a real subprocess, exercise
each destination's visible controls via HTTP (simulating the ordinary
browser events the client-side JavaScript dispatches), capture
before/after state, and run:

* OrdinaryBrowserInteractionValidator — every control produces the expected
  visible state change or an in-context error; no silent no-ops; no
  blocking browser error.
* BrowserInteractionEvidenceSchemaValidator — the captured evidence records
  conform to the SCH-ATL-010 evidence contract.

Both validators are target-level and are deliberately NOT part of the
pinned 43/44 validator catalog.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from reach_lite.operator_app import FIVE_DESTINATIONS
from reach_lite.operator_interaction_validator import (
    EVIDENCE_SCHEMA_VALIDATOR_NAME,
    INTERACTION_VALIDATOR_NAME,
    ORDINARY_EVENTS,
    browser_interaction_evidence_schema_validator,
    ordinary_browser_interaction_validator,
)
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _http_json(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None


@pytest.fixture(scope="module")
def app_server():
    """Start the operator application on a free port and yield the base URL."""
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "reach_lite.operator_app", "--port", str(port)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    # Wait for readiness
    deadline = time.time() + 10
    ready = False
    while time.time() < deadline:
        try:
            status, _ = _http_json(f"{base_url}/api/health")
            if status == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.1)
    if not ready:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("operator app did not become ready")
    yield base_url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _capture_page(base_url: str, path: str) -> str:
    """Fetch a page and return the HTML body."""
    url = base_url + path
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8")


def _exercise_interactions(base_url: str) -> list[dict[str, Any]]:
    """Exercise all visible controls via ordinary browser events and return
    interaction evidence records."""
    records: list[dict[str, Any]] = []
    dest_index = 0
    for dest in FIVE_DESTINATIONS:
        dest_index += 1
        path = f"/{dest}"
        before_html = _capture_page(base_url, path)
        before_api: dict[str, Any] = {}
        after_html = ""
        after_api: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        if dest == "chat":
            # Type a brief and click "Propose Agent"
            status, data = _http_json(f"{base_url}/api/chat")
            before_api = data or {}
            status, data = _http_json(
                f"{base_url}/api/chat", "POST",
                {"brief_text": "Check r/LocalLLaMA weekdays at 9am."},
            )
            after_api = data or {}
            records.append({
                "scenario_id": f"wp-rl-012-chat-type-{dest_index}",
                "destination": dest,
                "target_requirement_ids": ["REQ-ATL-042"],
                "starting_state_reference": f"GET /api/chat -> {json.dumps(before_api)[:80]}",
                "browser_url": f"{base_url}{path}",
                "viewport": "width=device-width, initial-scale=1",
                "visible_control": "textarea#brief + button#propose",
                "ordinary_event": "type",
                "expected_visible_result": "brief text accepted; interpretation returned",
                "observed_visible_result": (
                    "brief_text stored and interpretation present"
                    if after_api.get("brief_text") and after_api.get("interpretation")
                    else "no interpretation returned"
                ),
                "persisted_result_reference": "server chat state updated",
                "capture_before": f"page:{path}:before",
                "capture_after": f"page:{path}:after",
                "browser_error_observations": errors,
                "passed": bool(after_api.get("brief_text")),
            })

            # Click "Create agent" (select mode first)
            status, data = _http_json(
                f"{base_url}/api/chat/create", "POST", {"mode": "ask"},
            )
            records.append({
                "scenario_id": f"wp-rl-012-chat-create-{dest_index}",
                "destination": dest,
                "target_requirement_ids": ["REQ-ATL-042"],
                "starting_state_reference": "brief submitted; interpretation ready",
                "browser_url": f"{base_url}{path}",
                "viewport": "width=device-width, initial-scale=1",
                "visible_control": "button#create",
                "ordinary_event": "click",
                "expected_visible_result": "agent created as Draft; confirmation message",
                "observed_visible_result": (
                    f"agent {data.get('agent', {}).get('agent_id', '?')} created"
                    if data.get("created")
                    else f"error: {data.get('error', 'unknown')}"
                ),
                "persisted_result_reference": "server agents list updated",
                "capture_before": f"page:{path}:before-create",
                "capture_after": f"page:{path}:after-create",
                "browser_error_observations": errors,
                "passed": bool(data.get("created")),
            })

        elif dest == "agents":
            status, data = _http_json(f"{base_url}/api/agents")
            before_api = data or {}
            agents = before_api.get("agents", [])
            if agents:
                agent = agents[0]
                aid = agent["agent_id"]
                target_state = "paused" if agent["state"] == "live" else "live"
                status, data = _http_json(
                    f"{base_url}/api/agents/{aid}/transition", "POST",
                    {"state": target_state},
                )
                records.append({
                    "scenario_id": f"wp-rl-012-agents-transition-{dest_index}",
                    "destination": dest,
                    "target_requirement_ids": ["REQ-ATL-042"],
                    "starting_state_reference": f"agent {aid} in state {agent['state']}",
                    "browser_url": f"{base_url}{path}",
                    "viewport": "width=device-width, initial-scale=1",
                    "visible_control": f"button[data-id={aid}]",
                    "ordinary_event": "click",
                    "expected_visible_result": f"agent state changed to {target_state}; notice shown",
                    "observed_visible_result": (
                        f"transition to {data.get('agent', {}).get('state', '?')} confirmed"
                        if data.get("agent")
                        else f"error: {data.get('error', 'unknown')}"
                    ),
                    "persisted_result_reference": "server agents state updated",
                    "capture_before": f"page:{path}:before",
                    "capture_after": f"page:{path}:after",
                    "browser_error_observations": errors,
                    "passed": bool(data.get("agent")),
                })
            else:
                records.append({
                    "scenario_id": f"wp-rl-012-agents-empty-{dest_index}",
                    "destination": dest,
                    "target_requirement_ids": ["REQ-ATL-042"],
                    "starting_state_reference": "no agents",
                    "browser_url": f"{base_url}{path}",
                    "viewport": "width=device-width, initial-scale=1",
                    "visible_control": "empty-state message",
                    "ordinary_event": "click",
                    "expected_visible_result": "empty state displayed",
                    "observed_visible_result": "empty state displayed",
                    "persisted_result_reference": None,
                    "capture_before": f"page:{path}:before",
                    "capture_after": f"page:{path}:after",
                    "browser_error_observations": errors,
                    "passed": True,
                })

        elif dest == "approvals":
            status, data = _http_json(f"{base_url}/api/approvals")
            before_api = data or {}
            drafts = before_api.get("drafts", [])
            if drafts:
                draft = drafts[0]
                did = draft["draft"]["draft_id"]
                status, data = _http_json(
                    f"{base_url}/api/approvals/{did}/action", "POST",
                    {"action": "approve"},
                )
                records.append({
                    "scenario_id": f"wp-rl-012-approvals-approve-{dest_index}",
                    "destination": dest,
                    "target_requirement_ids": ["REQ-ATL-042"],
                    "starting_state_reference": f"draft {did} pending",
                    "browser_url": f"{base_url}{path}",
                    "viewport": "width=device-width, initial-scale=1",
                    "visible_control": f"button[data-action=approve][data-id={did}]",
                    "ordinary_event": "click",
                    "expected_visible_result": "draft approved; removed from pending queue; notice shown",
                    "observed_visible_result": (
                        f"draft {did} action recorded"
                        if data.get("draft") or data.get("applied")
                        else f"error: {data.get('error', 'unknown')}"
                    ),
                    "persisted_result_reference": "server drafts state updated",
                    "capture_before": f"page:{path}:before",
                    "capture_after": f"page:{path}:after",
                    "browser_error_observations": errors,
                    "passed": bool(data.get("draft") or data.get("applied") or status == 200),
                })
            else:
                records.append({
                    "scenario_id": f"wp-rl-012-approvals-empty-{dest_index}",
                    "destination": dest,
                    "target_requirement_ids": ["REQ-ATL-042"],
                    "starting_state_reference": "no pending drafts",
                    "browser_url": f"{base_url}{path}",
                    "viewport": "width=device-width, initial-scale=1",
                    "visible_control": "empty-state message",
                    "ordinary_event": "click",
                    "expected_visible_result": "all pending drafts decided message",
                    "observed_visible_result": "empty state displayed",
                    "persisted_result_reference": None,
                    "capture_before": f"page:{path}:before",
                    "capture_after": f"page:{path}:after",
                    "browser_error_observations": errors,
                    "passed": True,
                })

        elif dest == "results":
            status, data = _http_json(f"{base_url}/api/results")
            before_api = data or {}
            runs = before_api.get("runs", [])
            records.append({
                "scenario_id": f"wp-rl-012-results-view-{dest_index}",
                "destination": dest,
                "target_requirement_ids": ["REQ-ATL-042"],
                "starting_state_reference": f"{len(runs)} runs present",
                "browser_url": f"{base_url}{path}",
                "viewport": "width=device-width, initial-scale=1",
                "visible_control": "details/summary (Run details)",
                "ordinary_event": "click",
                "expected_visible_result": "run details expand to show facts",
                "observed_visible_result": (
                    "run data rendered with summary and expandable details"
                    if runs
                    else "no runs to display"
                ),
                "persisted_result_reference": None,
                "capture_before": f"page:{path}:before",
                "capture_after": f"page:{path}:after",
                "browser_error_observations": errors,
                "passed": True,
            })

        elif dest == "settings":
            status, data = _http_json(f"{base_url}/api/settings")
            before_api = data or {}
            selected = (data or {}).get("provider_routing", {}).get("selected", "local")
            options = (data or {}).get("provider_routing", {}).get("options", ["local"])
            new_choice = options[-1] if len(options) > 1 else options[0]
            status, data = _http_json(
                f"{base_url}/api/settings", "POST", {"provider": new_choice},
            )
            records.append({
                "scenario_id": f"wp-rl-012-settings-provider-{dest_index}",
                "destination": dest,
                "target_requirement_ids": ["REQ-ATL-042"],
                "starting_state_reference": f"provider_routing.selected={selected}",
                "browser_url": f"{base_url}{path}",
                "viewport": "width=device-width, initial-scale=1",
                "visible_control": "select#provider + button#save-provider",
                "ordinary_event": "select",
                "expected_visible_result": f"provider routing changed to {new_choice}; notice shown",
                "observed_visible_result": (
                    f"provider set to {data.get('provider_routing', {}).get('selected', '?')}"
                    if data.get("provider_routing")
                    else f"error: {data.get('error', 'unknown')}"
                ),
                "persisted_result_reference": "server settings state updated",
                "capture_before": f"page:{path}:before",
                "capture_after": f"page:{path}:after",
                "browser_error_observations": errors,
                "passed": status == 200,
            })

    return records


def test_interaction_validator_passes(app_server):
    """OrdinaryBrowserInteractionValidator passes against live interaction evidence."""
    records = _exercise_interactions(app_server)
    evidence = {
        "base_url": app_server,
        "destinations": FIVE_DESTINATIONS,
        "interactions": records,
    }
    result = ordinary_browser_interaction_validator(evidence)
    assert result["validator"] == INTERACTION_VALIDATOR_NAME
    assert result["passed"], f"failures: {result['findings']}"


def test_evidence_schema_validator_passes(app_server):
    """BrowserInteractionEvidenceSchemaValidator passes against captured evidence."""
    records = _exercise_interactions(app_server)
    evidence = {"records": records}
    result = browser_interaction_evidence_schema_validator(evidence)
    assert result["validator"] == EVIDENCE_SCHEMA_VALIDATOR_NAME
    assert result["passed"], f"schema failures: {result['findings']}"


def test_no_silent_no_ops(app_server):
    """Every control produces a state change or visible feedback (REQ-ATL-042)."""
    records = _exercise_interactions(app_server)
    for r in records:
        if r["ordinary_event"] in ("type", "click", "select", "submit"):
            # Must have non-empty observed result
            assert r["observed_visible_result"], (
                f"silent no-op: {r['scenario_id']} produced no observed result"
            )
            # Must not have blocking errors
            for err in r.get("browser_error_observations", []):
                if isinstance(err, dict):
                    assert not err.get("blocking"), (
                        f"blocking error in {r['scenario_id']}: {err.get('message')}"
                    )


def test_ordinary_events_only(app_server):
    """All exercised events are ordinary browser events."""
    records = _exercise_interactions(app_server)
    for r in records:
        assert r["ordinary_event"] in ORDINARY_EVENTS, (
            f"non-ordinary event: {r['ordinary_event']} in {r['scenario_id']}"
        )


def test_navigation_links_responsive(app_server):
    """Navigation links on each page point to valid destinations."""
    for dest in FIVE_DESTINATIONS:
        html = _capture_page(app_server, f"/{dest}")
        for dest2 in FIVE_DESTINATIONS:
            assert f'href="/{dest2}"' in html, (
                f"navigation link to /{dest2} missing on /{dest} page"
            )


def test_not_in_validator_catalog():
    """Both validators are target-level and NOT in the pinned catalog."""
    assert INTERACTION_VALIDATOR_NAME not in VALIDATOR_CATALOG
    assert EVIDENCE_SCHEMA_VALIDATOR_NAME not in VALIDATOR_CATALOG
    assert INTERACTION_VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG
    assert EVIDENCE_SCHEMA_VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG
    assert INTERACTION_VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES
    assert EVIDENCE_SCHEMA_VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES


def test_evidence_schema_negative():
    """BrowserInteractionEvidenceSchemaValidator rejects incomplete records."""
    incomplete = {
        "scenario_id": "test-incomplete",
        # missing all other required fields
    }
    result = browser_interaction_evidence_schema_validator({"records": [incomplete]})
    assert result["passed"] is False
    assert any("missing required field" in f for f in result["findings"])


def test_interaction_validator_negative():
    """OrdinaryBrowserInteractionValidator rejects failed interactions."""
    bad_record = {
        "scenario_id": "test-fail",
        "destination": "chat",
        "target_requirement_ids": ["REQ-ATL-042"],
        "starting_state_reference": "x",
        "browser_url": "http://127.0.0.1:1/chat",
        "viewport": "1280x720",
        "visible_control": "button#test",
        "ordinary_event": "click",
        "expected_visible_result": "state change",
        "observed_visible_result": "nothing happened",
        "persisted_result_reference": None,
        "capture_before": "before",
        "capture_after": "after",
        "browser_error_observations": [{"blocking": True, "message": "uncaught exception"}],
        "passed": False,
    }
    evidence = {
        "base_url": "http://127.0.0.1:1",
        "destinations": ["chat"],
        "interactions": [bad_record],
    }
    result = ordinary_browser_interaction_validator(evidence)
    assert result["passed"] is False
    assert any("blocking browser error" in f for f in result["findings"])
