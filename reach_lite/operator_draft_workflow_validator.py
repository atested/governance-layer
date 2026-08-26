"""DraftWorkflowInteractionValidator (REQ-ATL-044, WP-RL-014).

Target-level validator over the delivered operator application for the
browser-driven Draft decision workflow.  It is deliberately kept OUT of the
pinned 43/44 validator catalog.

Passes when a browser scenario lets the operator inspect a pending Draft's
review context and complete every supported Draft decision path -- approve,
edit-and-approve, regenerate, and skip -- separately from a visible pending
item, each through visible application controls only.  For every decision
path the evidence must show:

  - a visible pending item as the starting state,
  - the source and qualification context displayed for review,
  - a visible feedback result from the control,
  - a reconciled queue (the decided Draft leaves the pending queue) and a
    persisted Draft outcome that matches the visible outcome,
  - only ordinary browser events on visible controls -- no direct interface,
    developer-tool, or manual data operation anywhere in the sequence,
  - step evidence conforming to the SCH-ATL-010 BrowserInteractionEvidence
    contract.
"""

from __future__ import annotations

from typing import Any

from .operator_interaction_validator import (
    EVIDENCE_REQUIRED_FIELDS,
    ORDINARY_EVENTS,
)
from .validators import _result

DRAFT_WORKFLOW_VALIDATOR_NAME = "DraftWorkflowInteractionValidator"

# The supported Draft decision paths the operator can complete from a
# visible pending item, matching the local approval actions (WP-RL-005).
REQUIRED_DECISION_PATHS = ("approve", "edit_approve", "regenerate", "skip")


def _decision_step_checks(decision: dict[str, Any], idx: int, findings: list[str]) -> None:
    """Validate the SCH-ATL-010 step evidence and workflow properties for one
    decision path."""
    label = decision.get("decision_path") or f"decision-{idx + 1}"
    steps = decision.get("steps", [])

    if not decision.get("visible_pending_item"):
        findings.append(f"{label}: no visible pending item recorded as starting state")
    if not decision.get("review_context_displayed"):
        findings.append(f"{label}: source/qualification review context not displayed")
    if not decision.get("visible_feedback"):
        findings.append(f"{label}: no visible feedback result recorded")

    if not steps:
        findings.append(f"{label}: no browser interaction steps supplied")
    for i, step in enumerate(steps):
        sid = step.get("scenario_id") or f"{label}-step-{i + 1}"
        for field in EVIDENCE_REQUIRED_FIELDS:
            if field not in step:
                findings.append(f"{sid}: missing required field '{field}'")
        event = step.get("ordinary_event", "")
        if event not in ORDINARY_EVENTS:
            findings.append(
                f"{sid}: event '{event}' is not an ordinary browser event "
                "(direct interface / developer-tool / manual data operation)"
            )
        if not step.get("visible_control"):
            findings.append(f"{sid}: no visible control identified")
        if step.get("passed") is False:
            findings.append(
                f"{sid}: expected '{step.get('expected_visible_result', '')}' "
                f"but observed '{step.get('observed_visible_result', '')}'"
            )
        errors = step.get("browser_error_observations", [])
        if isinstance(errors, list):
            for err in errors:
                if isinstance(err, dict) and err.get("blocking", False):
                    findings.append(
                        f"{sid}: blocking browser error: {err.get('message', 'unknown')}"
                    )

    # Queue reconciliation: a decided Draft must leave the pending queue.
    queue = decision.get("queue_state")
    if queue is None:
        findings.append(f"{label}: no queue state recorded")
    elif queue.get("decided_leaves_pending") is False:
        findings.append(f"{label}: decided Draft did not leave the pending queue")

    # Persisted outcome must reconcile with the visible outcome.
    visible = decision.get("final_visible_state")
    persisted = decision.get("final_persisted_state")
    if visible is None or persisted is None:
        findings.append(f"{label}: missing final visible or persisted outcome")
    elif visible != persisted:
        findings.append(
            f"{label}: final visible outcome does not match persisted outcome: "
            + repr({"visible": visible, "persisted": persisted})
        )


def draft_workflow_interaction_validator(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate that every supported Draft decision path was completed through
    visible controls with reconciled queue and persisted outcome.

    The evidence dict must contain:
      - scenario_id: stable identifier
      - base_url: authoritative application URL
      - viewport: declared viewport
      - target_requirement_ids: list of requirement ids (REQ-ATL-044)
      - decisions: list of per-decision-path evidence, each with:
          decision_path, visible_pending_item, review_context_displayed,
          visible_feedback, steps (SCH-ATL-010 BrowserInteractionEvidence),
          queue_state, final_visible_state, final_persisted_state
      - used_non_visible_operations: list of any direct interface,
        developer-tool, or manual data operations that were attempted
    """
    scenario_id = evidence.get("scenario_id", "draft-workflow")
    base_url: str = evidence.get("base_url", "")
    viewport: str = evidence.get("viewport", "")
    decisions: list[dict[str, Any]] = evidence.get("decisions", [])
    target_ids: list[str] = [scenario_id]
    findings: list[str] = []

    if not base_url:
        findings.append("evidence missing base_url")
    if not viewport:
        findings.append("evidence missing viewport")
    if not decisions:
        findings.append("no Draft decision evidence supplied")

    present_paths = [d.get("decision_path") for d in decisions if d.get("decision_path")]
    for path in REQUIRED_DECISION_PATHS:
        if path not in present_paths:
            findings.append(f"missing supported decision path: {path}")

    for idx, decision in enumerate(decisions):
        label = decision.get("decision_path") or f"decision-{idx + 1}"
        if decision.get("decision_path") not in REQUIRED_DECISION_PATHS:
            findings.append(f"{label}: unknown decision path")
        _decision_step_checks(decision, idx, findings)

    # No non-visible operations anywhere in the sequence.
    non_visible = evidence.get("used_non_visible_operations", [])
    if non_visible:
        findings.append("sequence used non-visible operations: " + repr(non_visible))

    passed = not findings
    return _result(DRAFT_WORKFLOW_VALIDATOR_NAME, target_ids, passed, findings, [])
