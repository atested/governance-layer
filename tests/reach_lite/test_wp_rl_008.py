"""WP-RL-008: one directly runnable operator application behind the
five-destination dashboard (REQ-ATL-036, GATE-RL-006).

Live tests start the application as a real subprocess
("python3 -m reach_lite.operator_app") and drive it over HTTP from a
prepared self-host environment; the target-level validator then runs over
evidence collected from that live target. Negative tests exercise each
VALCAT v1.1 finding class in isolation.
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

import pytest

from reach_lite.domain import PROHIBITED_OPERATOR_CONTROLS
from reach_lite.operator_app import APP_NAME, FIVE_DESTINATIONS
from reach_lite.operator_validator import (
    VALIDATOR_NAME,
    build_live_inventory,
    runnable_operator_application_validator,
)
from reach_lite.validators import COMPLETE_VALIDATOR_CATALOG, EXPECTED_VALIDATOR_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
DECLARED_OPERATION = "python3 -m reach_lite.operator_app --port {port}"


def _http(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            code = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        code = exc.code
    if "/api/" in url:
        return code, json.loads(raw) if raw.strip() else {}
    return code, raw


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def operator_app():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "reach_lite.operator_app", "--port", str(port), "--bind", "127.0.0.1"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    last_error: Exception | None = None
    healthy = False
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
            pytest.fail(f"operator application exited early (rc={proc.returncode}): {output}")
        try:
            status, body = _http(f"{base}/api/health")
            if status == 200:
                healthy = True
                break
        except Exception as exc:  # noqa: BLE001 - readiness probe
            last_error = exc
        time.sleep(0.1)
    if not healthy:
        proc.kill()
        pytest.fail(f"operator application never became healthy: {last_error}")
    yield {"base": base, "proc": proc, "port": port}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Entry point and five destinations (browser-rendered navigation)
# ---------------------------------------------------------------------------


def test_health_declares_single_entry_point(operator_app):
    status, body = _http(f"{operator_app['base']}/api/health")
    assert status == 200
    assert body["app"] == APP_NAME
    assert body["entry_point"] == "/"
    assert body["destinations"] == list(FIVE_DESTINATIONS)


def test_entry_point_renders_all_five_destinations(operator_app):
    base = operator_app["base"]
    status, html = _http(base + "/")
    assert status == 200
    assert isinstance(html, str)
    for dest in FIVE_DESTINATIONS:
        assert f'href="/{dest}"' in html
        route_status, route_html = _http(f"{base}/{dest}")
        assert route_status == 200
        assert f"view-{dest}" in route_html


# ---------------------------------------------------------------------------
# Integrated current-scope behavior behind the entry point
# ---------------------------------------------------------------------------


def test_chat_brief_to_agent_proposal(operator_app):
    base = operator_app["base"]
    brief = (
        "Check r/LocalLLaMA weekdays at 9am, qualify local model releases, "
        "exclude vendor promotion, maximum 2 drafts"
    )
    status, body = _http(base + "/api/chat", method="POST", payload={"brief_text": brief})
    assert status == 200
    interpretation = body["interpretation"]
    assert interpretation["schedule"]["cadence"] == "weekly"
    assert interpretation["schedule"]["time"] == "09:00"
    assert interpretation["sources"] == [{"kind": "subreddit", "value": "r/LocalLLaMA"}]
    # Exact values as produced by the accepted domain interpret_brief.
    assert interpretation["qualifier"]["include"] == "local model releases,"
    assert interpretation["qualifier"]["exclude"] == "vendor promotion,"
    assert interpretation["budget"]["max_drafts_per_run"] == 2
    assert body["clarifications"] == []
    choices = body["proposal"]["choices"]
    assert "create_agent" in choices
    assert "not_now" in choices

    # The same interpretation is visible on the chat surface.
    get_status, chat = _http(base + "/api/chat")
    assert get_status == 200
    assert chat["brief_text"] == brief
    assert chat["interpretation"]["schedule"]["cadence"] == "weekly"


def test_agent_creation_and_lifecycle(operator_app):
    base = operator_app["base"]
    status, body = _http(
        base + "/api/agents",
        method="POST",
        payload={
            "agent_id": "agent-e2e",
            "brief_text": "Check r/LocalLLaMA weekdays at 9am.",
            "sources": [{"kind": "subreddit", "value": "r/LocalLLaMA"}],
            "qualifier": {"include": "local model releases"},
            "mode": "ask",
        },
    )
    assert status == 200
    assert body["agent"]["state"] == "draft"

    status, live = _http(base + "/api/agents/agent-e2e/transition", method="POST", payload={"state": "live"})
    assert status == 200
    assert live["agent"]["state"] == "live"

    status, paused = _http(base + "/api/agents/agent-e2e/transition", method="POST", payload={"state": "paused"})
    assert status == 200
    assert paused["agent"]["state"] == "paused"

    status, rejected = _http(base + "/api/agents/agent-e2e/transition", method="POST", payload={"state": "bogus"})
    assert status == 409


def test_results_reconciled_to_domain_accounts(operator_app):
    base = operator_app["base"]
    status, body = _http(base + "/api/results")
    assert status == 200
    assert len(body["runs"]) == 1
    run = body["runs"][0]["run"]
    summary = body["runs"][0]["summary"]
    assert run["run_id"] == "run-001"
    assert run["status"] == "succeeded"
    assert summary["candidates_seen"] == 12
    assert summary["candidates_qualified"] == 3
    assert summary["drafts_produced"] == 3
    assert sum(summary["drafts_by_state"].values()) == 3


def test_settings_current_scope_only(operator_app):
    base = operator_app["base"]
    status, body = _http(base + "/api/settings")
    assert status == 200
    rendered = json.dumps(body)
    for control in body["current_scope"]:
        assert control["enabled"] is True
    for control in body["deferred"]:
        assert control["enabled"] is False
    for prohibited in PROHIBITED_OPERATOR_CONTROLS:
        assert prohibited not in rendered


def test_approval_actions_drive_domain_state(operator_app):
    base = operator_app["base"]
    status, body = _http(base + "/api/approvals")
    assert status == 200
    pending = [entry["draft"] for entry in body["drafts"]]
    assert len(pending) == 3
    assert all(d["state"] == "pending" for d in pending)
    # Review context carries the five required classes.
    context = body["drafts"][0]["review_context"]
    assert set(context) == {"source", "body", "channel", "target", "qualification_reason"}

    draft_1 = pending[0]["draft_id"]
    status, approved = _http(f"{base}/api/approvals/{draft_1}/action", method="POST", payload={"action": "approve"})
    assert status == 200
    assert approved["draft"]["state"] == "approved"

    draft_2 = pending[1]["draft_id"]
    status, edited = _http(
        f"{base}/api/approvals/{draft_2}/action",
        method="POST",
        payload={"action": "edit_approve", "new_body": "Edited operator copy."},
    )
    assert status == 200
    assert edited["draft"]["state"] == "edited"
    assert edited["draft"]["body"] == "Edited operator copy."

    draft_3 = pending[2]["draft_id"]
    status, regenerated = _http(
        f"{base}/api/approvals/{draft_3}/action",
        method="POST",
        payload={"action": "regenerate", "new_body": "Regenerated copy.", "new_draft_id": "draft-regen-e2e"},
    )
    assert status == 200
    assert regenerated["draft"]["state"] == "pending"
    assert regenerated["draft"]["draft_id"] == "draft-regen-e2e"

    status, skipped = _http(
        f"{base}/api/approvals/draft-regen-e2e/action", method="POST", payload={"action": "skip"}
    )
    assert status == 200
    assert skipped["draft"]["state"] == "rejected"

    status, unknown = _http(
        f"{base}/api/approvals/draft-regen-e2e/action", method="POST", payload={"action": "delete"}
    )
    assert status == 400

    status, remaining = _http(base + "/api/approvals")
    assert status == 200
    assert remaining["drafts"] == []


# ---------------------------------------------------------------------------
# Target-level validator (RunnableOperatorApplicationValidator)
# ---------------------------------------------------------------------------


def test_validator_passes_against_live_target(operator_app):
    inventory = build_live_inventory(
        operator_app["base"],
        pid=operator_app["proc"].pid,
        declared_operation=DECLARED_OPERATION.format(port=operator_app["port"]),
        environment_prepared=True,
    )
    result = runnable_operator_application_validator(inventory)
    assert result["validator"] == VALIDATOR_NAME
    assert result["passed"] is True
    assert result["findings"] == []
    assert result["evidence_refs"]


def test_validator_is_not_part_of_the_pinned_catalog():
    assert VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES
    assert VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG


def _good_inventory() -> dict:
    return {
        "target_id": "operator-app",
        "environment": {"prepared_self_host": True},
        "activation": {"declared_operation": "python3 -m reach_lite.operator_app --port 9700"},
        "process_evidence": {"pid": 4242, "alive": True, "started_by_activation": True},
        "navigation": {
            "entry_point": "http://127.0.0.1:9700",
            "destinations": {
                dest: {"rendered": True, "evidence": f"GET /{dest} -> 200"}
                for dest in FIVE_DESTINATIONS
            },
        },
        "inventory": {"targets": [{"path": "reach_lite/operator_app.py", "kind": "application"}]},
    }


def _finding_kinds(result: dict) -> set:
    return {f["finding"] for f in result["findings"]}


def test_finding_non_runnable_target_without_process():
    inventory = _good_inventory()
    inventory["process_evidence"] = {"pid": None, "alive": False, "started_by_activation": False}
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    assert "non-runnable-target" in _finding_kinds(result)


def test_finding_non_runnable_target_without_operation():
    inventory = _good_inventory()
    inventory["activation"] = {}
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    assert "non-runnable-target" in _finding_kinds(result)


def test_finding_non_runnable_target_with_multiple_operations():
    inventory = _good_inventory()
    inventory["activation"] = {
        "declared_operations": [
            "python3 -m reach_lite.operator_app --port 9700",
            "python3 -m other_app",
        ]
    }
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    assert "non-runnable-target" in _finding_kinds(result)


def test_finding_fragmented_surface_with_two_entry_points():
    inventory = _good_inventory()
    inventory["navigation"]["entry_points"] = ["http://127.0.0.1:9700", "http://127.0.0.1:9701"]
    inventory["navigation"].pop("entry_point", None)
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    assert "fragmented-surface" in _finding_kinds(result)


def test_finding_missing_destination():
    inventory = _good_inventory()
    inventory["navigation"]["destinations"].pop("settings", None)
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    kinds = _finding_kinds(result)
    assert "missing-destination" in kinds
    assert any("settings" in f["detail"] for f in result["findings"] if f["finding"] == "missing-destination")


def test_finding_component_only_inventory():
    inventory = _good_inventory()
    inventory["inventory"]["targets"] = [
        {"path": "reach_lite/domain.py", "kind": "library"},
        {"path": "reach_lite/reconciliation.py", "kind": "fixture"},
        {"path": "reach_lite/validators.py", "kind": "validator"},
        {"path": "reach_lite/components.py", "kind": "component"},
    ]
    result = runnable_operator_application_validator(inventory)
    assert result["passed"] is False
    assert "component-only" in _finding_kinds(result)
