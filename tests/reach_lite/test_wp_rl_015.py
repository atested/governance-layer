"""WP-RL-015: recoverable failure feedback and terminal gate reconciliation."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any

import pytest

from reach_lite.operator_app import _dashboard_html, _destination_html, create_app, seed_state
from reach_lite.operator_failure_validator import (
    FAILURE_FEEDBACK_VALIDATOR_NAME,
    RELEASE_GATE_VALIDATOR_NAME,
    REQUIRED_FAILURE_SCENARIOS,
    REQUIRED_RELEASE_VALIDATORS,
    interaction_failure_feedback_validator,
    release_gate_reconciliation_validator,
)

VIEWPORT = "1280x720"


def _http_json(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


@pytest.fixture()
def failing_app():
    state = seed_state(set(REQUIRED_FAILURE_SCENARIOS))
    server, state = create_app(port=0, state=state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _record(base_url: str, scenario: str, path: str, control: str) -> dict[str, Any]:
    return {
        "scenario_id": f"wp-rl-015-{scenario}",
        "target_requirement_ids": ["REQ-ATL-045"],
        "starting_state_reference": f"{scenario}:state-before",
        "browser_url": base_url + path,
        "viewport": VIEWPORT,
        "visible_control": control,
        "ordinary_event": "click",
        "expected_visible_result": "specific in-workflow error with recoverable state",
        "observed_visible_result": "specific in-workflow error; state retained",
        "persisted_result_reference": f"{scenario}:state-after",
        "capture_before": f"capture:{scenario}:before",
        "capture_after": f"capture:{scenario}:after",
        "browser_error_observations": [],
        "passed": True,
    }


def _failure_scenario(
    base_url: str,
    name: str,
    path: str,
    control: str,
    before: Any,
    after: Any,
    error: str,
) -> dict[str, Any]:
    return {
        "scenario": name,
        "relevant_state_before": before,
        "relevant_state_after": after,
        "visible_error": error,
        "error_near_workflow": True,
        "retry_available": True,
        "safe_navigation_available": True,
        "blank_response": False,
        "raw_exception": False,
        "silent_noop": False,
        "destructive_state_loss": False,
        "interaction_evidence": _record(base_url, name, path, control),
    }


def test_all_five_failures_preserve_server_state_and_return_specific_feedback(failing_app):
    base_url, state = failing_app
    scenarios: list[dict[str, Any]] = []

    # Prepare an editable proposal, then fail creation before state mutation.
    _http_json(
        base_url + "/api/chat",
        "POST",
        {"brief_text": "Check r/LocalLLaMA weekdays at 9am for local releases."},
    )
    before = {"chat": dict(state.chat), "agent_count": len(state.agents)}
    status, response = _http_json(base_url + "/api/chat/create", "POST", {"mode": "ask"})
    after = {"chat": dict(state.chat), "agent_count": len(state.agents)}
    assert status == 503 and response["recoverable"] is True
    scenarios.append(_failure_scenario(base_url, "creation", "/chat", "button#create", before, after, response["error"]))

    agent = state.agents[0]
    before = {"agent_id": agent.agent_id, "state": agent.state}
    status, response = _http_json(
        base_url + f"/api/agents/{agent.agent_id}/transition", "POST", {"state": "paused"}
    )
    unchanged = next(item for item in state.agents if item.agent_id == agent.agent_id)
    after = {"agent_id": unchanged.agent_id, "state": unchanged.state}
    assert status == 503
    scenarios.append(_failure_scenario(base_url, "lifecycle_change", "/agents", "button[data-state]", before, after, response["error"]))

    draft = state.drafts[0]
    before = {"draft_id": draft.draft_id, "body": draft.body, "state": draft.state}
    status, response = _http_json(
        base_url + f"/api/approvals/{draft.draft_id}/action", "POST",
        {"action": "edit_approve", "new_body": "Operator edited copy"},
    )
    unchanged = next(item for item in state.drafts if item.draft_id == draft.draft_id)
    after = {"draft_id": unchanged.draft_id, "body": unchanged.body, "state": unchanged.state}
    assert status == 503
    scenarios.append(_failure_scenario(base_url, "draft_decision", "/approvals", "button[data-action=edit_approve]", before, after, response["error"]))

    before = {"selected": state.provider_routing, "attempted": "codex"}
    status, response = _http_json(base_url + "/api/settings", "POST", {"provider": "codex"})
    after = {"selected": state.provider_routing, "attempted": "codex"}
    assert status == 503
    scenarios.append(_failure_scenario(base_url, "provider_routing", "/settings", "button#save-provider", before, after, response["error"]))

    before = {"runs": len(state.runs), "drafts": len(state.drafts)}
    status, response = _http_json(base_url + "/api/settings/export")
    after = {"runs": len(state.runs), "drafts": len(state.drafts)}
    assert status == 503
    scenarios.append(_failure_scenario(base_url, "export", "/settings", "button#export", before, after, response["error"]))

    result = interaction_failure_feedback_validator({"scenarios": scenarios})
    assert result["validator"] == FAILURE_FEEDBACK_VALIDATOR_NAME
    assert result["passed"] is True, result["findings"]


def test_failure_validator_rejects_blank_raw_silent_and_destructive_results():
    scenarios = {}
    for name in REQUIRED_FAILURE_SCENARIOS:
        scenarios[name] = {
            "state_preserved": True,
            "visible_error": "Please try again.",
            "error_near_workflow": True,
            "retry_available": True,
            "interaction_evidence": _record("http://127.0.0.1:9700", name, "/", "button"),
        }
    scenarios["creation"].update(
        visible_error="Traceback (most recent call last): ValueError",
        raw_exception=True,
        silent_noop=True,
        destructive_state_loss=True,
    )
    result = interaction_failure_feedback_validator({"scenarios": scenarios})
    assert result["passed"] is False
    text = " | ".join(result["findings"])
    assert "raw exception" in text
    assert "silent no-op" in text
    assert "destructive state loss" in text


def _release_evidence() -> dict[str, Any]:
    results = {
        name: {
            "validator": name,
            "target_ids": ["operator-app"],
            "passed": True,
            "findings": [],
            "evidence_refs": [f"evidence:{name}"],
        }
        for name in REQUIRED_RELEASE_VALIDATORS
    }
    surfaces = {
        "entry-point": {
            "status": 200,
            "html": _dashboard_html(),
            "url": "http://127.0.0.1:9700/",
        },
        **{
            name: {
                "status": 200,
                "html": _destination_html(name),
                "url": f"http://127.0.0.1:9700/{name}",
            }
            for name in ("chat", "agents", "approvals", "results", "settings")
        },
    }
    return {
        "validator_results": results,
        "rendered_surface_evidence": {
            "viewport": {"declared": "width=device-width, initial-scale=1"},
            "surfaces": surfaces,
        },
        "browser_interaction_evidence": [
            _record("http://127.0.0.1:9700", "release-gate", "/chat", "button#propose")
        ],
    }


def test_terminal_release_gate_requires_all_passing_validators_and_rendered_interactions():
    evidence = _release_evidence()
    result = release_gate_reconciliation_validator(evidence)
    assert result["validator"] == RELEASE_GATE_VALIDATOR_NAME
    assert result["passed"] is True, result["findings"]

    evidence["validator_results"].pop("StyledOperatorSurfaceValidator")
    evidence["rendered_surface_evidence"] = {}
    evidence["browser_interaction_evidence"] = []
    result = release_gate_reconciliation_validator(evidence)
    assert result["passed"] is False
    assert any("StyledOperatorSurfaceValidator" in item for item in result["findings"])
    assert any("rendered operator-surface" in item for item in result["findings"])
    assert any("interaction-driven" in item for item in result["findings"])


def test_ui_routes_contain_in_workflow_failure_feedback_and_retry_preservation(failing_app):
    base_url, _state = failing_app
    for path in ("/chat", "/agents", "/approvals", "/settings"):
        with urllib.request.urlopen(base_url + path, timeout=5) as response:
            html = response.read().decode()
        assert "workflowError" in html
        assert "workflow-error" in html
        assert "role','alert" in html
    with urllib.request.urlopen(base_url + "/settings", timeout=5) as response:
        settings_html = response.read().decode()
    assert "window.location='/api/settings/export'" not in settings_html
    assert "await api('/api/settings/export')" in settings_html
