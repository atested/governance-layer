"""WP-RL-015 failure feedback and terminal release-gate reconciliation.

The validators in this module operate on evidence captured from the delivered
operator application.  They intentionally remain outside the pinned source
validator catalog: InteractionFailureFeedbackValidator covers REQ-ATL-045,
while OperatorApplicationReleaseGateReconciliationValidator joins the source
catalog with the target-level launch, surface, and browser-workflow gates.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .operator_interaction_validator import (
    EVIDENCE_REQUIRED_FIELDS,
    ORDINARY_EVENTS,
    browser_interaction_evidence_schema_validator,
)
from .operator_surface_validator import styled_operator_surface_validator
from .validators import COMPLETE_VALIDATOR_CATALOG, _result

FAILURE_FEEDBACK_VALIDATOR_NAME = "InteractionFailureFeedbackValidator"
RELEASE_GATE_VALIDATOR_NAME = "OperatorApplicationReleaseGateReconciliationValidator"

REQUIRED_FAILURE_SCENARIOS = (
    "creation",
    "lifecycle_change",
    "draft_decision",
    "provider_routing",
    "export",
)

TARGET_LEVEL_RELEASE_VALIDATORS = (
    "RunnableOperatorApplicationValidator",
    "DurableLaunchInstructionsValidator",
    "ActivationProfileSchemaValidator",
    "ConfiguredActivationProfileValidator",
    "BrowserOpenableUrlValidator",
    "EndToEndLaunchHealthValidator",
    "StyledOperatorSurfaceValidator",
    "OrdinaryBrowserInteractionValidator",
    "BrowserInteractionEvidenceSchemaValidator",
    "AgentWorkflowInteractionValidator",
    "DraftWorkflowInteractionValidator",
    FAILURE_FEEDBACK_VALIDATOR_NAME,
)

REQUIRED_RELEASE_VALIDATORS = (
    *tuple(COMPLETE_VALIDATOR_CATALOG),
    *TARGET_LEVEL_RELEASE_VALIDATORS,
)

_SCENARIO_ALIASES = {
    "agent_creation": "creation",
    "create_agent": "creation",
    "agent_lifecycle": "lifecycle_change",
    "lifecycle": "lifecycle_change",
    "draft": "draft_decision",
    "approval": "draft_decision",
    "provider": "provider_routing",
    "run_log_export": "export",
}
_RAW_ERROR_RE = re.compile(
    r"(?:traceback \(most recent call last\)|\b(?:type|value|runtime|key|attribute)error\b|"
    r"\bexception\b|\bat [\w.$<>]+\([^\n]*:\d+\))",
    re.IGNORECASE,
)


def _scenario_name(scenario: Mapping[str, Any]) -> str:
    value = (
        scenario.get("scenario")
        or scenario.get("failure_scenario")
        or scenario.get("workflow")
        or scenario.get("name")
        or ""
    )
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return _SCENARIO_ALIASES.get(normalized, normalized)


def _scenario_list(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenarios = evidence.get("scenarios", [])
    if isinstance(scenarios, Mapping):
        return [
            dict(value, scenario=key) if isinstance(value, Mapping) else {"scenario": key}
            for key, value in scenarios.items()
        ]
    if isinstance(scenarios, list):
        return [dict(item) for item in scenarios if isinstance(item, Mapping)]
    return []


def _browser_record(scenario: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("interaction_evidence", "browser_evidence", "interaction", "step"):
        value = scenario.get(key)
        if isinstance(value, Mapping):
            return value
    if any(field in scenario for field in EVIDENCE_REQUIRED_FIELDS):
        return scenario
    return None


def _visible_error(scenario: Mapping[str, Any]) -> str:
    value = (
        scenario.get("visible_error")
        or scenario.get("error_message")
        or scenario.get("human_readable_error")
        or ""
    )
    return value.strip() if isinstance(value, str) else ""


def _state_preserved(scenario: Mapping[str, Any]) -> bool:
    flags = (
        "state_preserved",
        "recoverable_state_preserved",
        "input_preserved",
        "selected_item_preserved",
    )
    explicit = [scenario.get(key) for key in flags if key in scenario]
    if explicit:
        return all(value is True for value in explicit)
    before_present = "relevant_state_before" in scenario or "state_before" in scenario
    after_present = "relevant_state_after" in scenario or "state_after" in scenario
    before = scenario.get("relevant_state_before", scenario.get("state_before"))
    after = scenario.get("relevant_state_after", scenario.get("state_after"))
    return before_present and after_present and before == after


def interaction_failure_feedback_validator(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Validate all five user-triggered failure scenarios against REQ-ATL-045.

    Each scenario records the relevant state before and after the failed
    action, an in-workflow visible error, retry or safe-navigation affordance,
    and one SCH-ATL-010 browser interaction record.
    """
    scenarios = _scenario_list(evidence)
    findings: list[str] = []
    target_ids: list[str] = []
    by_name: dict[str, dict[str, Any]] = {}

    for scenario in scenarios:
        name = _scenario_name(scenario)
        if not name:
            findings.append("failure scenario has no stable workflow name")
            continue
        if name in by_name:
            findings.append(f"{name}: duplicate failure scenario evidence")
            continue
        by_name[name] = scenario
        target_ids.append(name)

    for required in REQUIRED_FAILURE_SCENARIOS:
        if required not in by_name:
            findings.append(f"missing failure scenario: {required}")

    schema_records: list[dict[str, Any]] = []
    for name, scenario in by_name.items():
        if name not in REQUIRED_FAILURE_SCENARIOS:
            findings.append(f"{name}: unknown failure scenario")

        error = _visible_error(scenario)
        if not error:
            findings.append(f"{name}: blank visible failure response")
        elif _RAW_ERROR_RE.search(error) or error.lstrip().startswith(("{", "[")):
            findings.append(f"{name}: raw exception or serialized error exposed to operator")

        near_workflow = scenario.get(
            "error_near_workflow", scenario.get("in_context_error", False)
        )
        if near_workflow is not True:
            findings.append(f"{name}: error was not displayed near the affected workflow")

        if not _state_preserved(scenario):
            findings.append(f"{name}: relevant operator state was not preserved")

        retry = scenario.get("retry_available", scenario.get("can_retry", False))
        safe_navigation = scenario.get(
            "safe_navigation_available", scenario.get("can_navigate_safely", False)
        )
        if retry is not True and safe_navigation is not True:
            findings.append(f"{name}: neither retry nor safe navigation remained available")

        for flag, detail in (
            ("blank_response", "blank response recorded"),
            ("raw_exception", "raw exception recorded"),
            ("silent_noop", "silent no-op recorded"),
            ("destructive_state_loss", "destructive state loss recorded"),
        ):
            if scenario.get(flag) is True:
                findings.append(f"{name}: {detail}")

        record = _browser_record(scenario)
        if record is None:
            findings.append(f"{name}: no interaction-driven SCH-ATL-010 evidence")
            continue
        schema_records.append(dict(record))
        if record.get("ordinary_event") not in ORDINARY_EVENTS:
            findings.append(f"{name}: failure was not triggered by an ordinary browser event")
        if record.get("passed") is not True:
            findings.append(f"{name}: failure-feedback browser scenario did not pass")

    schema_result = browser_interaction_evidence_schema_validator({"records": schema_records})
    if not schema_result["passed"]:
        findings.extend(
            f"browser evidence: {finding}" for finding in schema_result["findings"]
        )

    return _result(
        FAILURE_FEEDBACK_VALIDATOR_NAME,
        target_ids or ["REQ-ATL-045"],
        not findings,
        findings,
        list(evidence.get("evidence_refs") or []),
    )


def _result_map(value: Any) -> dict[str, Mapping[str, Any]]:
    if isinstance(value, Mapping):
        results: dict[str, Mapping[str, Any]] = {}
        for key, item in value.items():
            if isinstance(item, Mapping):
                name = item.get("validator") or key
                results[str(name)] = item
        return results
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return {
            str(item.get("validator")): item
            for item in value
            if isinstance(item, Mapping) and item.get("validator")
        }
    return {}


def release_gate_reconciliation_validator(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Reconcile the complete source and operator-application release gate.

    A passing claim requires every source-catalog and target-level validator
    result, plus the actual rendered-surface inventory and SCH-ATL-010 browser
    records used by the target-level results.  A result list alone cannot
    satisfy this terminal gate.
    """
    results = _result_map(
        evidence.get("validator_results", evidence.get("results", {}))
    )
    findings: list[str] = []

    for name in REQUIRED_RELEASE_VALIDATORS:
        result = results.get(name)
        if result is None:
            findings.append(f"release gate missing validator result: {name}")
        elif result.get("passed") is not True:
            findings.append(f"release gate validator did not pass: {name}")

    surface_inventory = evidence.get("rendered_surface_evidence") or evidence.get(
        "surface_inventory"
    )
    surfaces = surface_inventory.get("surfaces") if isinstance(surface_inventory, Mapping) else None
    required_surfaces = ("entry-point", "chat", "agents", "approvals", "results", "settings")
    if not isinstance(surfaces, Mapping):
        findings.append("release gate has no rendered operator-surface inventory")
    else:
        for name in required_surfaces:
            surface = surfaces.get(name)
            if not isinstance(surface, Mapping) or surface.get("status") != 200 or not surface.get("html"):
                findings.append(f"rendered operator-surface evidence missing or unsuccessful: {name}")
        surface_result = styled_operator_surface_validator(dict(surface_inventory))
        if not surface_result["passed"]:
            findings.extend(
                "release-gate rendered evidence: " + str(finding)
                for finding in surface_result["findings"]
            )

    records = evidence.get("browser_interaction_evidence") or evidence.get(
        "interaction_records"
    )
    if not isinstance(records, list) or not records:
        findings.append("release gate has no interaction-driven browser evidence")
    else:
        schema_result = browser_interaction_evidence_schema_validator({"records": records})
        if not schema_result["passed"]:
            findings.extend(
                f"release-gate browser evidence: {finding}"
                for finding in schema_result["findings"]
            )
        for record in records:
            if not isinstance(record, Mapping):
                continue
            if not record.get("capture_before") or not record.get("capture_after"):
                findings.append(
                    f"{record.get('scenario_id', '<unknown>')}: rendered before/after capture absent"
                )

    return _result(
        RELEASE_GATE_VALIDATOR_NAME,
        list(REQUIRED_RELEASE_VALIDATORS),
        not findings,
        findings,
        list(evidence.get("evidence_refs") or []),
    )
