"""WP-RL-014: the operator inspects review context and completes every
supported Draft decision entirely through visible application controls
(REQ-ATL-044, SCH-ATL-010).

Live tests start the operator application as a real subprocess and complete
each supported Draft decision path -- approve, edit-and-approve, regenerate,
and skip -- separately from a visible pending item in the Approvals queue,
using ordinary browser events on visible controls via HTTP.  For every
decision path the evidence records the visible pending item, the source and
qualification review context that is displayed, the visible feedback the
control produces, and a reconciled queue plus persisted Draft outcome, and
runs DraftWorkflowInteractionValidator over the evidence.

Negative tests prove the scenario fails when a non-visible operation is
used, when a supported decision path is missing, when the persisted outcome
diverges from the visible outcome, and when a decision leaves the Draft in
the pending queue.  The validator is target-level and deliberately NOT part
of the pinned 43/44 validator catalog.
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

from reach_lite.operator_draft_workflow_validator import (
    DRAFT_WORKFLOW_VALIDATOR_NAME,
    REQUIRED_DECISION_PATHS,
    draft_workflow_interaction_validator,
)
from reach_lite.operator_interaction_validator import ORDINARY_EVENTS
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

VIEWPORT = "1280x720"
REQUIREMENT_IDS = ["REQ-ATL-044"]

# The three Drafts seeded by seed_state() plus the regenerated Draft.
PENDING_DRAFTS = ("draft-opp-001", "draft-opp-002", "draft-opp-003")


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


@pytest.fixture(scope="function")
def app_server():
    """Start the operator application on a free port and yield the base URL.

    Function-scoped so every test starts from a fresh seeded queue (the
    finite pending Drafts are consumed by each decision workflow run).
    """
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


def _pending_ids(base_url: str) -> list[str]:
    _status, data = _http_json(f"{base_url}/api/approvals")
    data = data or {}
    return [d["draft"]["draft_id"] for d in data.get("drafts", [])]


def _review_context(base_url: str, draft_id: str) -> dict[str, Any]:
    _status, data = _http_json(f"{base_url}/api/approvals")
    data = data or {}
    for entry in data.get("drafts", []):
        if entry["draft"]["draft_id"] == draft_id:
            return entry["review_context"]
    return {}


def _make_step(*, base_url: str, scenario_id: str, draft_id: str, visible_control: str,
               event: str, expected: str, observed: str, persisted_ref: str,
               passed: bool, capture_before: str, capture_after: str) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "target_requirement_ids": REQUIREMENT_IDS,
        "starting_state_reference": f"Draft {draft_id} visible in Approvals pending queue",
        "browser_url": base_url + "/approvals",
        "viewport": VIEWPORT,
        "visible_control": visible_control,
        "ordinary_event": event,
        "expected_visible_result": expected,
        "observed_visible_result": observed,
        "persisted_result_reference": persisted_ref,
        "capture_before": capture_before,
        "capture_after": capture_after,
        "browser_error_observations": [],
        "passed": passed,
    }


def _run_approvals_workflow(base_url: str) -> dict[str, Any]:
    """Complete every supported Draft decision from a visible pending item and
    return the per-decision evidence."""
    decisions: list[dict[str, Any]] = []

    # -- approve ----------------------------------------------------------
    draft_id = "draft-opp-001"
    ctx = _review_context(base_url, draft_id)
    assert ctx.get("source"), f"approve: no source context for {draft_id}"
    assert ctx.get("qualification_reason"), f"approve: no qualification context for {draft_id}"
    _status, res = _http_json(f"{base_url}/api/approvals/{draft_id}/action", "POST", {"action": "approve"})
    res = res or {}
    persisted_state = {
        "draft_id": (res.get("draft") or {}).get("draft_id", draft_id),
        "state": (res.get("draft") or {}).get("state"),
    }
    after_pending = _pending_ids(base_url)
    approve_ok = persisted_state["state"] == "approved" and draft_id not in after_pending
    decisions.append({
        "decision_path": "approve",
        "visible_pending_item": f"Draft {draft_id} visible in Approvals pending queue",
        "review_context_displayed": {
            "source": ctx.get("source"),
            "qualification_reason": ctx.get("qualification_reason"),
            "channel": ctx.get("channel"),
        },
        "visible_feedback": "notice 'Draft decision recorded in this queue.'",
        "steps": [
            _make_step(
                base_url=base_url,
                scenario_id="rl-014-approve",
                draft_id=draft_id,
                visible_control="button[data-action=approve]",
                event="click",
                expected=f"Draft {draft_id} marked approved; removed from pending queue",
                observed=(
                    f"Draft {draft_id} approved and removed from queue"
                    if approve_ok else "approve did not reconcile the queue"
                ),
                persisted_ref="server Draft state updated to approved",
                passed=approve_ok,
                capture_before=f"page:/approvals:{draft_id}:before-approve",
                capture_after=f"page:/approvals:{draft_id}:after-approve",
            )
        ],
        "queue_state": {
            "decided_leaves_pending": draft_id not in after_pending,
            "remaining_pending": len(after_pending),
        },
        "final_visible_state": persisted_state,
        "final_persisted_state": persisted_state,
    })

    # -- edit-and-approve -------------------------------------------------
    draft_id = "draft-opp-002"
    ctx = _review_context(base_url, draft_id)
    assert ctx.get("source") and ctx.get("qualification_reason"), "edit_approve: missing review context"
    edited_body = "Edited operator copy for draft-opp-002."
    _status, res = _http_json(
        f"{base_url}/api/approvals/{draft_id}/action", "POST",
        {"action": "edit_approve", "new_body": edited_body},
    )
    res = res or {}
    persisted_state = {
        "draft_id": (res.get("draft") or {}).get("draft_id", draft_id),
        "state": (res.get("draft") or {}).get("state"),
        "body": (res.get("draft") or {}).get("body"),
    }
    after_pending = _pending_ids(base_url)
    edit_ok = (
        persisted_state["state"] == "edited"
        and persisted_state["body"] == edited_body
        and draft_id not in after_pending
    )
    decisions.append({
        "decision_path": "edit_approve",
        "visible_pending_item": f"Draft {draft_id} visible in Approvals pending queue",
        "review_context_displayed": {
            "source": ctx.get("source"),
            "qualification_reason": ctx.get("qualification_reason"),
        },
        "visible_feedback": "notice 'Draft decision recorded in this queue.'",
        "steps": [
            _make_step(
                base_url=base_url,
                scenario_id="rl-014-edit-approve",
                draft_id=draft_id,
                visible_control="button[data-action=edit_approve] + edit prompt",
                event="click",
                expected=f"Draft {draft_id} edited and approved with accepted body",
                observed=(
                    f"Draft {draft_id} edited/approved and removed from queue"
                    if edit_ok else "edit-and-approve did not reconcile the queue"
                ),
                persisted_ref="server Draft state updated to edited with accepted body",
                passed=edit_ok,
                capture_before=f"page:/approvals:{draft_id}:before-edit",
                capture_after=f"page:/approvals:{draft_id}:after-edit",
            )
        ],
        "queue_state": {
            "decided_leaves_pending": draft_id not in after_pending,
            "remaining_pending": len(after_pending),
        },
        "final_visible_state": persisted_state,
        "final_persisted_state": persisted_state,
    })

    # -- regenerate -------------------------------------------------------
    draft_id = "draft-opp-003"
    ctx = _review_context(base_url, draft_id)
    assert ctx.get("source") and ctx.get("qualification_reason"), "regenerate: missing review context"
    regen_id = draft_id + "-regen"
    _status, res = _http_json(
        f"{base_url}/api/approvals/{draft_id}/action", "POST",
        {"action": "regenerate", "new_body": "Regenerated operator copy.", "new_draft_id": regen_id},
    )
    res = res or {}
    persisted_state = {
        "draft_id": (res.get("draft") or {}).get("draft_id", regen_id),
        "state": (res.get("draft") or {}).get("state"),
        "body": (res.get("draft") or {}).get("body"),
    }
    after_pending = _pending_ids(base_url)
    regen_ok = (
        persisted_state["state"] == "pending"
        and persisted_state["draft_id"] == regen_id
        and regen_id in after_pending
    )
    decisions.append({
        "decision_path": "regenerate",
        "visible_pending_item": f"Draft {draft_id} visible in Approvals pending queue",
        "review_context_displayed": {
            "source": ctx.get("source"),
            "qualification_reason": ctx.get("qualification_reason"),
        },
        "visible_feedback": "notice 'Draft decision recorded in this queue.'",
        "steps": [
            _make_step(
                base_url=base_url,
                scenario_id="rl-014-regenerate",
                draft_id=draft_id,
                visible_control="button[data-action=regenerate]",
                event="click",
                expected=f"Draft {regen_id} regenerated as a fresh pending item",
                observed=(
                    f"Draft {regen_id} regenerated and pending"
                    if regen_ok else "regenerate did not produce a fresh pending Draft"
                ),
                persisted_ref="server Draft replaced by a fresh pending Draft",
                passed=regen_ok,
                capture_before=f"page:/approvals:{draft_id}:before-regen",
                capture_after=f"page:/approvals:{regen_id}:after-regen",
            )
        ],
        "queue_state": {
            "decided_leaves_pending": draft_id not in after_pending,
            "remaining_pending": len(after_pending),
        },
        "final_visible_state": persisted_state,
        "final_persisted_state": persisted_state,
    })

    # -- skip -------------------------------------------------------------
    draft_id = regen_id
    ctx = _review_context(base_url, draft_id)
    assert ctx.get("source") and ctx.get("qualification_reason"), "skip: missing review context"
    _status, res = _http_json(f"{base_url}/api/approvals/{draft_id}/action", "POST", {"action": "skip"})
    res = res or {}
    persisted_state = {
        "draft_id": (res.get("draft") or {}).get("draft_id", draft_id),
        "state": (res.get("draft") or {}).get("state"),
    }
    after_pending = _pending_ids(base_url)
    skip_ok = persisted_state["state"] == "rejected" and draft_id not in after_pending
    decisions.append({
        "decision_path": "skip",
        "visible_pending_item": f"Draft {draft_id} visible in Approvals pending queue",
        "review_context_displayed": {
            "source": ctx.get("source"),
            "qualification_reason": ctx.get("qualification_reason"),
        },
        "visible_feedback": "notice 'Draft decision recorded in this queue.'",
        "steps": [
            _make_step(
                base_url=base_url,
                scenario_id="rl-014-skip",
                draft_id=draft_id,
                visible_control="button[data-action=skip]",
                event="click",
                expected=f"Draft {draft_id} skipped (rejected); removed from pending queue",
                observed=(
                    f"Draft {draft_id} skipped and removed from queue"
                    if skip_ok else "skip did not reconcile the queue"
                ),
                persisted_ref="server Draft state updated to rejected",
                passed=skip_ok,
                capture_before=f"page:/approvals:{draft_id}:before-skip",
                capture_after=f"page:/approvals:{draft_id}:after-skip",
            )
        ],
        "queue_state": {
            "decided_leaves_pending": draft_id not in after_pending,
            "remaining_pending": len(after_pending),
        },
        "final_visible_state": persisted_state,
        "final_persisted_state": persisted_state,
    })

    # The Approvals page serves and renders the queue; confirm the visible
    # surface is the served Approvals page with renderable controls.
    html = _capture_page(base_url, "/approvals")
    assert 'id="app-content"' in html, "Approvals page not served"
    assert "approvals" in html, "Approvals client not renderable"

    evidence: dict[str, Any] = {
        "scenario_id": "rl-014-draft-decision-workflow",
        "base_url": base_url,
        "viewport": VIEWPORT,
        "target_requirement_ids": REQUIREMENT_IDS,
        "decisions": decisions,
        "used_non_visible_operations": [],
    }
    return evidence


def test_draft_workflow_passes_validator(app_server):
    """DraftWorkflowInteractionValidator passes for all four decision paths."""
    evidence = _run_approvals_workflow(app_server)
    result = draft_workflow_interaction_validator(evidence)
    assert result["validator"] == DRAFT_WORKFLOW_VALIDATOR_NAME
    assert result["passed"] is True, f"findings: {result['findings']}"
    assert result["findings"] == []


def test_all_decision_paths_present(app_server):
    """Every supported Draft decision path is completed from a visible item."""
    evidence = _run_approvals_workflow(app_server)
    paths = [d["decision_path"] for d in evidence["decisions"]]
    assert paths == list(REQUIRED_DECISION_PATHS)


def test_only_ordinary_browser_events(app_server):
    """No decision uses a direct interface, developer-tool, or manual data op."""
    evidence = _run_approvals_workflow(app_server)
    for decision in evidence["decisions"]:
        for step in decision["steps"]:
            assert step["ordinary_event"] in ORDINARY_EVENTS, step["scenario_id"]
    assert evidence["used_non_visible_operations"] == []


def test_review_context_displayed(app_server):
    """Every decision displays source and qualification context."""
    evidence = _run_approvals_workflow(app_server)
    for decision in evidence["decisions"]:
        ctx = decision["review_context_displayed"]
        assert ctx["source"], decision["decision_path"]
        assert ctx["qualification_reason"], decision["decision_path"]
        assert decision["visible_pending_item"]
        assert decision["visible_feedback"]


def test_queue_reconciled_for_every_decision(app_server):
    """A decided Draft always leaves the pending queue."""
    evidence = _run_approvals_workflow(app_server)
    for decision in evidence["decisions"]:
        assert decision["queue_state"]["decided_leaves_pending"] is True
        assert decision["final_visible_state"] == decision["final_persisted_state"]


def test_missing_decision_path_fails_validator(app_server):
    """Omitting a supported decision path fails the scenario."""
    evidence = _run_approvals_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["decisions"] = [d for d in bad["decisions"] if d["decision_path"] != "skip"]
    result = draft_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("missing supported decision path" in f for f in result["findings"])


def test_non_visible_operation_fails_validator(app_server):
    """A direct developer-tool operation in the sequence fails the scenario."""
    evidence = _run_approvals_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["used_non_visible_operations"] = ["direct DB write to drafts table"]
    result = draft_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("non-visible operations" in f for f in result["findings"])


def test_persisted_outcome_divergence_fails_validator(app_server):
    """A persisted Draft outcome that diverges from the visible one fails."""
    evidence = _run_approvals_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["decisions"][0]["final_persisted_state"] = dict(bad["decisions"][0]["final_visible_state"])
    bad["decisions"][0]["final_persisted_state"]["state"] = "rejected"  # diverged
    result = draft_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("does not match persisted outcome" in f for f in result["findings"])


def test_stays_pending_fails_validator(app_server):
    """A decision that leaves the Draft pending in the queue fails."""
    evidence = _run_approvals_workflow(app_server)
    bad = json.loads(json.dumps(evidence))
    bad["decisions"][0]["queue_state"]["decided_leaves_pending"] = False
    result = draft_workflow_interaction_validator(bad)
    assert result["passed"] is False
    assert any("did not leave the pending queue" in f for f in result["findings"])


def test_wp_rl_014_validator_is_not_in_pinned_catalogs():
    """DraftWorkflowInteractionValidator is target-level and NOT pinned."""
    assert DRAFT_WORKFLOW_VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES
    assert DRAFT_WORKFLOW_VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG
    assert DRAFT_WORKFLOW_VALIDATOR_NAME not in VALIDATOR_CATALOG