"""AgentWorkflowInteractionValidator (REQ-ATL-043, WP-RL-013).

Target-level validator over the delivered operator application for the
primary Agent workflow.  It is deliberately kept OUT of the pinned
43/44 validator catalog.

Passes when a browser scenario completes the primary Agent workflow
entirely through visible application controls:
  enter brief in Chat -> receive proposal card -> edit proposal card ->
  create Agent -> locate it in Agents -> pause or resume it
using only ordinary browser events on visible controls, with final
visible and persisted state matching the actions taken, no direct
interface / developer-tool / manual data operation in the sequence,
and every step's evidence conforming to the SCH-ATL-010
BrowserInteractionEvidence contract.
"""

from __future__ import annotations

from typing import Any

from .operator_interaction_validator import (
    EVIDENCE_REQUIRED_FIELDS,
    ORDINARY_EVENTS,
)
from .validators import _result

WORKFLOW_VALIDATOR_NAME = "AgentWorkflowInteractionValidator"

# The primary Agent workflow, in the order the operator must complete it.
REQUIRED_WORKFLOW_STEPS = (
    "enter_brief",      # type a brief in Chat
    "receive_proposal", # receive the proposal card
    "edit_proposal",    # edit the proposal card
    "create_agent",     # create the Agent from the proposal
    "locate_agent",     # find the Agent in Agents
    "pause_resume",     # pause or resume the Agent
)


def agent_workflow_interaction_validator(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate that the primary Agent workflow completed through visible
    controls end to end with reconciled final state.

    The evidence dict must contain:
      - scenario_id: stable identifier
      - base_url: authoritative application URL
      - viewport: declared viewport
      - target_requirement_ids: list of requirement ids (REQ-ATL-043)
      - steps: list of BrowserInteractionEvidence records, each tagged with
        the workflow_step label it fulfils
      - final_visible_state: dict describing the final visible state
      - final_persisted_state: dict describing the final persisted state
      - used_non_visible_operations: list of any direct interface,
        developer-tool, or manual data operations that were attempted
    """
    scenario_id = evidence.get("scenario_id", "agent-workflow")
    base_url: str = evidence.get("base_url", "")
    viewport: str = evidence.get("viewport", "")
    steps: list[dict[str, Any]] = evidence.get("steps", [])
    target_ids: list[str] = [scenario_id]
    findings: list[str] = []

    if not base_url:
        findings.append("evidence missing base_url")
    if not viewport:
        findings.append("evidence missing viewport")
    if not steps:
        findings.append("no workflow interaction steps supplied")

    for i, step in enumerate(steps):
        sid = step.get("scenario_id") or f"step-{i + 1}"
        # SCH-ATL-010 schema conformance.
        for field in EVIDENCE_REQUIRED_FIELDS:
            if field not in step:
                findings.append(f"{sid}: missing required field '{field}'")
        # Ordinary browser event on a visible control.
        event = step.get("ordinary_event", "")
        if event not in ORDINARY_EVENTS:
            findings.append(
                f"{sid}: event '{event}' is not an ordinary browser event "
                "(direct interface / developer-tool / manual data operation)"
            )
        if not step.get("visible_control"):
            findings.append(f"{sid}: no visible control identified")
        # Outcome and errors.
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

    # Required workflow sequence, in order.
    step_labels = [s.get("workflow_step") for s in steps if s.get("workflow_step")]
    present_in_order = [label for label in step_labels if label in REQUIRED_WORKFLOW_STEPS]
    if present_in_order != list(REQUIRED_WORKFLOW_STEPS):
        findings.append(
            "workflow not completed in the required order; got "
            + repr(present_in_order)
        )

    # No non-visible operations anywhere in the sequence.
    non_visible = evidence.get("used_non_visible_operations", [])
    if non_visible:
        findings.append("sequence used non-visible operations: " + repr(non_visible))

    # Final visible and persisted state reconcile.
    visible = evidence.get("final_visible_state")
    persisted = evidence.get("final_persisted_state")
    if visible is None or persisted is None:
        findings.append("missing final visible or persisted state")
    elif visible != persisted:
        findings.append(
            "final visible state does not match persisted state: "
            + repr({"visible": visible, "persisted": persisted})
        )

    passed = not findings
    return _result(WORKFLOW_VALIDATOR_NAME, target_ids, passed, findings, [])
