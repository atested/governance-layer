"""Companion catalog acceptance for VALCAT-atested-reach-lite-f8de0e@1.1.

Runs every validator in the complete companion catalog -- the 43 source
validators plus ValidatorCatalogCompletenessValidator -- against the
conforming walking-skeleton reconciliation fixtures, then verifies the two
catalog-level acceptance properties:

1. every target reported by any validator resolves to a known entity value
   from the fixtures, a domain controlled-vocabulary value, a catalog entry
   name, or a documented derived label (scenario index, scenario action, or
   agent action pair); and
2. no prohibited scope appears in any fixture string or validator finding --
   no pipeline-stage surface, no attestation or operator-control capability,
   and no cryptographic claim marker.

The acceptance verdict passes only when every validator passes, every target
resolves, and no prohibited scope is present.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .domain import (
    AGENT_ACTIONS,
    AGENT_MODES,
    AGENT_STATES,
    APPROVAL_ACTIONS,
    CADENCES,
    CONNECTION_STATUSES,
    CRYPTO_CLAIM_MARKERS,
    DRAFT_STATES,
    INVOCATION_STATUSES,
    LOG_RECORD_TYPES,
    PIPELINE_STAGE_NAMES,
    PROVIDERS,
    PROHIBITED_ATTESTATION_CAPABILITIES,
    PROHIBITED_OPERATOR_CONTROLS,
    RUN_STATUSES,
    TASK_TYPES,
)
from .reconciliation import build_conforming_fixtures, run_reconciliation
from .validators import (
    AGENT_SCREEN_FIELDS,
    ALLOWED_AUTONOMOUS_TASKS,
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
)

# Every controlled vocabulary a target may legitimately reference, plus the
# fallback labels the validators emit when a fixture field is absent
# (ProviderSwapGate "activation", AgentCreationTime "creation") and the
# chat card fallback ids ("card-<index>").
_CONTROLLED_VOCABULARY: tuple[str, ...] = (
    AGENT_STATES
    + AGENT_ACTIONS
    + AGENT_MODES
    + CADENCES
    + RUN_STATUSES
    + DRAFT_STATES
    + CONNECTION_STATUSES
    + LOG_RECORD_TYPES
    + TASK_TYPES
    + PROVIDERS
    + INVOCATION_STATUSES
    + APPROVAL_ACTIONS
    + ALLOWED_AUTONOMOUS_TASKS
    + AGENT_SCREEN_FIELDS
    + EXPECTED_VALIDATOR_NAMES
    + ("activation", "creation", "card-0", "card-1", "card-2")
)

# Prohibited exact-match surfaces: pipeline stage names and deferred
# attestation/operator-control capabilities must never appear in fixture
# values.
_PROHIBITED_EXACT: tuple[str, ...] = (
    PIPELINE_STAGE_NAMES
    + PROHIBITED_ATTESTATION_CAPABILITIES
    + PROHIBITED_OPERATOR_CONTROLS
)


def _fixture_strings(value: Any) -> set[str]:
    """Collect every string value and string key reachable in a fixture."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                found.add(key)
            found |= _fixture_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found |= _fixture_strings(item)
    elif is_dataclass(value) and not isinstance(value, type):
        found |= _fixture_strings(asdict(value))
    elif isinstance(value, str):
        found.add(value)
    return found


def _derived_labels(fixtures: dict[str, Any]) -> set[str]:
    """Labels the validators derive from fixture structure rather than
    literal values: "scenario <index>", "scenario:<action>", and
    "<agent name>:<action>" pairs."""
    labels: set[str] = set()
    for fixture in fixtures.values():
        if not isinstance(fixture, dict):
            continue
        scenarios = fixture.get("scenarios")
        if isinstance(scenarios, (list, tuple)):
            for index in range(len(scenarios)):
                labels.add("scenario " + str(index))
            for scenario in scenarios:
                if isinstance(scenario, dict):
                    action = str(scenario.get("action") or "").strip().lower()
                    if action:
                        labels.add("scenario:" + action)
        actions = fixture.get("actions")
        if isinstance(actions, (list, tuple)):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                name = str(action.get("name") or "")
                verb = str(action.get("action") or "").strip().lower()
                if name and verb:
                    labels.add(name + ":" + verb)
    return labels


def _known_targets(fixtures: dict[str, Any]) -> set[str]:
    known: set[str] = set(_CONTROLLED_VOCABULARY)
    known |= set(COMPLETE_VALIDATOR_CATALOG)
    for fixture in fixtures.values():
        known |= _fixture_strings(fixture)
    known |= _derived_labels(fixtures)
    return known


def _prohibited_scope_findings(
    fixtures: dict[str, Any], results: dict[str, dict[str, Any]]
) -> list[str]:
    findings: list[str] = []
    texts: list[tuple[str, str]] = []
    for name, fixture in sorted(fixtures.items()):
        for value in sorted(_fixture_strings(fixture)):
            texts.append((name, value))
    for name, result in sorted(results.items()):
        for finding in result.get("findings", []):
            texts.append((name, str(finding)))
    for source, text in texts:
        lowered = text.strip().lower()
        if text in _PROHIBITED_EXACT:
            findings.append(
                "prohibited exact surface in " + source + ": " + repr(text)
            )
        elif any(marker in lowered for marker in CRYPTO_CLAIM_MARKERS):
            findings.append(
                "cryptographic claim marker in " + source + ": " + repr(text)
            )
    return findings


def accept_companion_catalog_1_1(
    fixtures: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the complete companion catalog and verify target resolution and
    the absence of prohibited scope.

    Returns a verdict with the per-validator results, catalog sizes, the
    count of resolved targets, any unresolved targets, any prohibited scope
    findings, and the overall passed flag.
    """
    if fixtures is None:
        fixtures = build_conforming_fixtures()
    report = run_reconciliation(fixtures)
    results: dict[str, dict[str, Any]] = report["results"]
    success_path_failures: dict[str, list[str]] = dict(report["failures"])

    known = _known_targets(fixtures)
    resolved = 0
    unresolved: list[str] = []
    for name, result in results.items():
        for target in result.get("target_ids", []):
            target = str(target)
            if target in known:
                resolved += 1
            else:
                unresolved.append(name + ":" + target)

    prohibited = _prohibited_scope_findings(fixtures, results)

    return {
        "results": results,
        "catalog_size": report["catalog_size"],
        "complete_catalog_size": report["complete_catalog_size"],
        "targets_resolved": resolved,
        "unresolved_targets": unresolved,
        "prohibited_scope_findings": prohibited,
        "passed": not success_path_failures and not unresolved and not prohibited,
        "success_path_failures": success_path_failures,
    }
