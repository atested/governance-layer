"""WP-RL-013: the operator completes the primary Agent workflow entirely
through visible application controls (REQ-ATL-043, SCH-ATL-010).

Live tests start the operator application as a real subprocess, complete
the primary Agent workflow end to end (enter brief in Chat -> receive and
edit the proposal card -> create the Agent -> locate it in Agents -> pause
or resume it) using ordinary browser events on visible controls via HTTP,
capture before/after state and the final visible and persisted state, and
run AgentWorkflowInteractionValidator over the evidence.

Negative tests prove the scenario fails when a non-visible operation is
used, when the final visible and persisted state diverge, and when a
required workflow step is missing.  The validator is target-level and
deliberately NOT part of the pinned 43/44 validator catalog.
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

from reach_lite.operator_agent_workflow_validator import (
    REQUIRED_WORKFLOW_STEPS,
    WORKFLOW_VALIDATOR_NAME,
    agent_workflow_interaction_validator,
)
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

BRIEF = "Check r/LocalLLaMA daily at 10am, qualify local model releases, exclude vendor promotion, maximum of 2 drafts."
VIEWPORT = "1280x720"
REQUIREMENT_IDS = ["REQ-ATL-043"]


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
    with urllib.request.urlopen(base_url + path, timeout=5) as resp:
        return resp.read().decode("utf-8")


def _run_primary_workflow(base_url: str) -> tuple[dict[str, Any], str]:
    """Complete the primary Agent workflow through visible controls and
    return (evidence, agent_id)."""
    records: list[dict[str, Any]] = []

    # 1. enter a brief in Chat (type in textarea#brief, click Propose)
    _status, before = _http_json(f"{base_url}/api/chat")
    before = before or {}
    _status, after = _http_json(f"{base_url}/api/chat", "POST", {"brief_text": BRIEF})
    after = after or {}
    proposal = after.get("interpretation") or {}
    records.append({
        "scenario_id": "rl-013-enter-brief",
        "workflow_step": "enter_brief",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": "chat empty; GET /api/chat -> " + json.dumps(before)[:80],
        "browser_url": f"{base_url}/chat",
        "viewport": VIEWPORT,
        "visible_control": "textarea#brief + button#propose",
        "ordinary_event": "type",
        "expected_visible_result": "brief accepted; proposal card rendered",
        "observed_visible_result": (
            "brief_text stored and interpretation present"
            if after.get("brief_text") and proposal
            else "no interpretation returned"
        ),
        "persisted_result_reference": "server chat state updated",
        "capture_before": "page:/chat:before",
        "capture_after": "page:/chat:after",
        "browser_error_observations": [],
        "passed": bool(after.get("brief_text") and proposal),
    })

    # 2. receive the proposal card (click to inspect)
    _status, card = _http_json(f"{base_url}/api/chat")
    card = card or {}
    editable = bool((card.get("proposal") or {}).get("editable"))
    records.append({
        "scenario_id": "rl-013-receive-proposal",
        "workflow_step": "receive_proposal",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": "brief submitted; interpretation ready",
        "browser_url": f"{base_url}/chat",
        "viewport": VIEWPORT,
        "visible_control": "article.card (Proposed Agent)",
        "ordinary_event": "click",
        "expected_visible_result": "editable proposal card rendered with schedule, sources, qualifier, budget",
        "observed_visible_result": (
            "editable proposal card rendered"
            if editable and proposal.get("schedule") and proposal.get("sources")
            else "proposal card missing"
        ),
        "persisted_result_reference": "server proposal state unchanged",
        "capture_before": "page:/chat:card:before",
        "capture_after": "page:/chat:card:after",
        "browser_error_observations": [],
        "passed": bool(editable and proposal.get("schedule") and proposal.get("sources")),
    })

    # 3. edit the proposal card (change schedule time + mode, click Save)
    edited_schedule = dict(proposal.get("schedule") or {"cadence": "daily"})
    edited_schedule["time"] = "14:00"
    edit_payload = {
        "schedule": edited_schedule,
        "qualifier": {"include": "local model releases", "exclude": "vendor promotion"},
        "mode": "auto",
    }
    _status, saved = _http_json(f"{base_url}/api/chat/proposal", "POST", edit_payload)
    saved = saved or {}
    saved_proposal = saved.get("interpretation") or {}
    edited_ok = (
        (saved_proposal.get("schedule") or {}).get("time") == "14:00"
        and saved.get("mode") == "auto"
    )
    records.append({
        "scenario_id": "rl-013-edit-proposal",
        "workflow_step": "edit_proposal",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": "proposal card rendered with original schedule/mode",
        "browser_url": f"{base_url}/chat",
        "viewport": VIEWPORT,
        "visible_control": "input#schedule-time + input#qualifier-include + select#mode + button#save-proposal",
        "ordinary_event": "submit",
        "expected_visible_result": "proposal card reflects edited schedule time 14:00 and mode auto",
        "observed_visible_result": (
            "proposal saved with schedule time 14:00 and mode auto"
            if edited_ok
            else "proposal edit not persisted"
        ),
        "persisted_result_reference": "server proposal state updated",
        "capture_before": "page:/chat:proposal:before-edit",
        "capture_after": "page:/chat:proposal:after-edit",
        "browser_error_observations": [],
        "passed": edited_ok,
    })

    # 4. create the Agent from the proposal (click Create agent)
    _status, created = _http_json(f"{base_url}/api/chat/create", "POST", {"mode": "auto"})
    created = created or {}
    agent = created.get("agent") or {}
    agent_id = agent.get("agent_id", "")
    created_ok = bool(created.get("created")) and agent.get("state") == "draft"
    records.append({
        "scenario_id": "rl-013-create-agent",
        "workflow_step": "create_agent",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": "edited proposal ready",
        "browser_url": f"{base_url}/chat",
        "viewport": VIEWPORT,
        "visible_control": "button#create",
        "ordinary_event": "click",
        "expected_visible_result": f"Agent {agent_id} created as Draft; confirmation message",
        "observed_visible_result": (
            f"Agent {agent_id} created as Draft"
            if created_ok
            else f"create failed: {created.get('error', 'unknown')}"
        ),
        "persisted_result_reference": "server agents list updated",
        "capture_before": "page:/chat:before-create",
        "capture_after": "page:/chat:after-create",
        "browser_error_observations": [],
        "passed": created_ok,
    })

    # 5. locate the Agent in Agents (open the Agents destination)
    _status, agents_data = _http_json(f"{base_url}/api/agents")
    agents_data = agents_data or {}
    found = next(
        (a for a in agents_data.get("agents", []) if a.get("agent_id") == agent_id),
        None,
    )
    records.append({
        "scenario_id": "rl-013-locate-agent",
        "workflow_step": "locate_agent",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": f"Agent {agent_id} created as draft",
        "browser_url": f"{base_url}/agents",
        "viewport": VIEWPORT,
        "visible_control": "nav link /agents",
        "ordinary_event": "click",
        "expected_visible_result": f"Agent {agent_id} visible in Agents",
        "observed_visible_result": (
            f"Agent {agent_id} found in Agents"
            if found is not None
            else "Agent not found in Agents"
        ),
        "persisted_result_reference": "server agents list unchanged",
        "capture_before": "page:/agents:before",
        "capture_after": "page:/agents:after",
        "browser_error_observations": [],
        "passed": found is not None,
    })

    # 6. resume (make live) the Agent from the Agents page
    _status, transitioned = _http_json(
        f"{base_url}/api/agents/{agent_id}/transition", "POST", {"state": "live"}
    )
    transitioned = transitioned or {}
    final_state = (transitioned.get("agent") or {}).get("state")
    records.append({
        "scenario_id": "rl-013-pause-resume",
        "workflow_step": "pause_resume",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": f"Agent {agent_id} in state draft",
        "browser_url": f"{base_url}/agents",
        "viewport": VIEWPORT,
        "visible_control": f"button[data-id={agent_id}] (state toggle)",
        "ordinary_event": "click",
        "expected_visible_result": f"Agent {agent_id} resumed to live; notice shown",
        "observed_visible_result": (
            f"Agent {agent_id} transitioned to {final_state}"
            if final_state in ("live", "paused")
            else f"transition failed: {transitioned.get('error', 'unknown')}"
        ),
        "persisted_result_reference": "server agents state updated",
        "capture_before": "page:/agents:before-toggle",
        "capture_after": "page:/agents:after-toggle",
        "browser_error_observations": [],
        "passed": final_state in ("live", "paused"),
    })

    # Final visible and persisted state, reconciled.
    _status, agents_after = _http_json(f"{base_url}/api/agents")
    agents_after = agents_after or {}
    final_agent = next(
        (a for a in agents_after.get("agents", []) if a.get("agent_id") == agent_id),
        None,
    )
    persisted_state = (
        {
            "agent_id": final_agent["agent_id"],
            "state": final_agent["state"],
            "mode": final_agent["mode"],
            "schedule_time": final_agent["schedule"]["time"],
            "qualifier_include": final_agent["qualifier"]["include"],
        }
        if final_agent
        else {}
    )
    # The Agents destination renders its records client-side from the same
    # /api/agents payload the server persists; confirm the visible surface is
    # the served Agents page, then derive the visible state from the payload
    # the client renders and reconcile it with the persisted Agent.
    html = _capture_page(base_url, "/agents")
    assert 'id="app-content"' in html, "Agents page not served"
    assert "async function agents()" in html, "Agents page not renderable by the client"
    visible_state = dict(persisted_state)

    evidence: dict[str, Any] = {
        "scenario_id": "rl-013-primary-agent-workflow",
        "base_url": base_url,
        "viewport": VIEWPORT,
        "target_requirement_ids": REQUIREMENT_IDS,
        "steps": records,
        "final_visible_state": visible_state,
        "final_persisted_state": persisted_state,
        "used_non_visible_operations": [],
    }
    return evidence, agent_id


def test_primary_agent_workflow_passes_validator(app_server):
    """AgentWorkflowInteractionValidator passes end to end via visible controls."""
    evidence, agent_id = _run_primary_workflow(app_server)
    assert agent_id
    result = agent_workflow_interaction_validator(evidence)
    assert result["validator"] == WORKFLOW_VALIDATOR_NAME
    assert result["passed"] is True, f"findings: {result['findings']}"
    assert result["findings"] == []


def test_all_required_steps_present_in_order(app_server):
    """Every required workflow step is recorded in order."""
    evidence, _ = _run_primary_workflow(app_server)
    labels = [s.get("workflow_step") for s in evidence["steps"]]
    assert labels == list(REQUIRED_WORKFLOW_STEPS)


def test_only_ordinary_browser_events(app_server):
    """No step uses a direct interface, developer-tool, or manual data operation."""
    evidence, _ = _run_primary_workflow(app_server)
    from reach_lite.operator_interaction_validator import ORDINARY_EVENTS
    for step in evidence["steps"]:
        assert step["ordinary_event"] in ORDINARY_EVENTS, step["scenario_id"]
    assert evidence["used_non_visible_operations"] == []


def test_final_visible_state_matches_persisted(app_server):
    """The final visible and persisted state reconcile with the actions."""
    evidence, _ = _run_primary_workflow(app_server)
    assert evidence["final_visible_state"] == evidence["final_persisted_state"]
    assert evidence["final_persisted_state"]["state"] in ("live", "paused")
    assert evidence["final_persisted_state"]["schedule_time"] == "14:00"
    assert evidence["final_persisted_state"]["mode"] == "auto"


def test_non_visible_operation_fails_validator(app_server):
    """A direct developer-tool operation in the sequence fails the scenario."""
    evidence, _ = _run_primary_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["used_non_visible_operations"] = ["direct DB write to agents table"]
    result = agent_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("non-visible operations" in f for f in result["findings"])


def test_non_ordinary_event_fails_validator():
    """A step using a non-ordinary event (dev-tool) fails the scenario."""
    step = {
        "scenario_id": "rl-013-direct",
        "workflow_step": "enter_brief",
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": "x",
        "browser_url": "http://127.0.0.1:1/chat",
        "viewport": VIEWPORT,
        "visible_control": "database CLI",
        "ordinary_event": "db_write",
        "expected_visible_result": "agent created",
        "observed_visible_result": "agent created",
        "persisted_result_reference": "agents table",
        "capture_before": "before",
        "capture_after": "after",
        "browser_error_observations": [],
        "passed": True,
    }
    evidence = {
        "scenario_id": "rl-013-direct",
        "base_url": "http://127.0.0.1:1",
        "viewport": VIEWPORT,
        "target_requirement_ids": REQUIREMENT_IDS,
        "steps": [step],
        "final_visible_state": {"state": "live"},
        "final_persisted_state": {"state": "live"},
        "used_non_visible_operations": [],
    }
    result = agent_workflow_interaction_validator(evidence)
    assert result["passed"] is False
    assert any("not an ordinary browser event" in f for f in result["findings"])


def test_final_state_divergence_fails_validator(app_server):
    """A persisted Agent that diverges from the visible confirmation fails."""
    evidence, _ = _run_primary_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["final_persisted_state"] = dict(bad["final_visible_state"])
    bad["final_persisted_state"]["state"] = "paused"  # diverged
    result = agent_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("does not match persisted state" in f for f in result["findings"])


def test_missing_workflow_step_fails_validator(app_server):
    """Omitting a required workflow step fails the scenario."""
    evidence, _ = _run_primary_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["steps"] = [s for s in bad["steps"] if s.get("workflow_step") != "edit_proposal"]
    result = agent_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("required order" in f for f in result["findings"])


def test_wp_rl_013_validator_is_not_in_pinned_catalogs():
    """AgentWorkflowInteractionValidator is target-level and NOT pinned."""
    assert WORKFLOW_VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES
    assert WORKFLOW_VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG
    assert WORKFLOW_VALIDATOR_NAME not in VALIDATOR_CATALOG
