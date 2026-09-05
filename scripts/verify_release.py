#!/usr/bin/env python3
"""Run the immutable Atested v2 release catalog and assemble its evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SPEC = "SPEC-atested-4eb81e0f@2.0"

# The order is the accepted requirement order. Keeping the mapping here makes
# omissions, duplicates, and substitutions release-blocking instead of allowing
# a package-local success to be mistaken for catalog conformance.
CATALOG: tuple[tuple[str, str, str], ...] = (
    ("WP-001", "REQ-ATESTED-001", "TransportBoundaryCoverageValidator"),
    ("WP-001", "REQ-ATESTED-002", "DeterministicPolicyClassificationValidator"),
    ("WP-001", "REQ-ATESTED-003", "PolicyOutcomeEnforcementValidator"),
    ("WP-002", "REQ-ATESTED-004", "PreExecutionDecisionRecordValidator"),
    ("WP-003", "REQ-ATESTED-005", "Tier3OpaqueApprovalGateValidator"),
    ("WP-003", "REQ-ATESTED-006", "ExplicitHumanApprovalOnlyValidator"),
    ("WP-003", "REQ-ATESTED-007", "ApprovalScopeLifetimeValidator"),
    ("WP-003", "REQ-ATESTED-008", "ApprovalRevocationValidator"),
    ("WP-003", "REQ-ATESTED-009", "NoDeveloperDenyBypassValidator"),
    ("WP-004", "REQ-ATESTED-010", "ProductionSigningRequiredValidator"),
    ("WP-004", "REQ-ATESTED-011", "UnsignedLocalDevelopmentBoundaryValidator"),
    ("WP-002", "REQ-ATESTED-012", "SignedChainIntegrityValidator"),
    ("WP-002", "REQ-ATESTED-013", "OperatorActionAttributionValidator"),
    ("WP-002", "REQ-ATESTED-014", "DenialReasonCodeValidator"),
    ("WP-005", "REQ-ATESTED-015", "OperatorDecisionReviewValidator"),
    ("WP-005", "REQ-ATESTED-016", "DashboardWindowModelValidator"),
    ("WP-004", "REQ-ATESTED-017", "NonRootProductionRuntimeValidator"),
    ("WP-004", "REQ-ATESTED-018", "GovernanceHealthStatusValidator"),
    ("WP-004", "REQ-ATESTED-019", "GovernanceOverloadSafetyValidator"),
    ("WP-008", "REQ-ATESTED-020", "PublishedDocumentationLinkValidator"),
    ("WP-001", "REQ-ATESTED-021", "GovernedSessionRoutingValidator"),
    ("WP-001", "REQ-ATESTED-022", "FourTierConsistencyValidator"),
    ("WP-001", "REQ-ATESTED-023", "DashboardUrlAccessValidator"),
    ("WP-006", "REQ-ATESTED-024", "LocalFirstContinuityValidator"),
    ("WP-005", "REQ-ATESTED-025", "DashboardInvestigationValidator"),
    ("WP-005", "REQ-ATESTED-026", "SummaryEvidenceTraceValidator"),
    ("WP-006", "REQ-ATESTED-027", "ScopedEvidencePackageValidator"),
    ("WP-004", "REQ-ATESTED-028", "UnsafeConditionRefusalValidator"),
    ("WP-007", "REQ-ATESTED-029", "AggregateOnlyTelemetryValidator"),
    ("WP-007", "REQ-ATESTED-030", "OptInAuthenticatedAiFeatureValidator"),
    ("WP-008", "REQ-ATESTED-031", "PublicContentEvidenceLanguageValidator"),
)

PACKAGE_ORDER = tuple(f"WP-{number:03d}" for number in range(1, 9))


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-spec", required=True)
    parser.add_argument("--validators", required=True, type=int)
    return parser.parse_args()


def _block(message: str, **details: object) -> int:
    result = {
        "release_result": "blocked",
        "source_spec": SOURCE_SPEC,
        "catalog_validator_count": len(CATALOG),
        "passed_validator_count": 0,
        "blocked_count": 1,
        "missing_evidence_count": 0,
        "reason": message,
        **details,
    }
    print(json.dumps(result, sort_keys=True), file=sys.stderr)
    return 1


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    return completed


def _json_evidence(output: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and {"validator", "element_id", "result"} <= value.keys():
            records.append(value)
    return records


def _evidence_paths(record: dict[str, object]) -> list[str]:
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
        return []
    return refs


def main() -> int:
    arguments = _arguments()
    if arguments.source_spec != SOURCE_SPEC:
        return _block("source specification does not match the accepted v2 authority")
    if arguments.validators != len(CATALOG):
        return _block("requested validator count does not match the immutable catalog")

    element_ids = [element for _, element, _ in CATALOG]
    validator_names = [validator for _, _, validator in CATALOG]
    if len(set(element_ids)) != len(CATALOG) or len(set(validator_names)) != len(CATALOG):
        return _block("release catalog contains duplicate requirements or validators")

    observed: list[dict[str, object]] = []
    for package in PACKAGE_ORDER:
        requested = [element for owner, element, _ in CATALOG if owner == package]
        completed = _run([
            sys.executable,
            str(ROOT / "scripts" / f"verify_wp_{package[-3:]}.py"),
            f"--elements={','.join(requested)}",
        ])
        if completed.returncode != 0:
            return _block(
                "package validator execution failed",
                failed_package=package,
                package_exit_code=completed.returncode,
            )
        observed.extend(_json_evidence(completed.stdout))

    expected = {(element, validator) for _, element, validator in CATALOG}
    actual = {
        (record.get("element_id"), record.get("validator"))
        for record in observed
    }
    if len(observed) != len(CATALOG) or actual != expected:
        return _block(
            "catalog evidence is incomplete or contains an unexpected validator identity",
            observed_validator_count=len(observed),
        )

    failed = [record for record in observed if record.get("result") != "pass"]
    if failed:
        return _block("one or more catalog validators did not pass", failed_evidence=failed)

    missing_evidence: list[dict[str, object]] = []
    for record in observed:
        refs = _evidence_paths(record)
        missing = [ref for ref in refs if not (ROOT / ref).is_file()]
        if not refs or missing:
            missing_evidence.append({
                "element_id": record.get("element_id"),
                "validator": record.get("validator"),
                "missing_refs": missing,
            })
    if missing_evidence:
        return _block(
            "validator evidence is missing or unresolved",
            missing_evidence_count=len(missing_evidence),
            missing_evidence=missing_evidence,
        )

    # Publication eligibility is not an extra validator: it is the completed
    # WP-009 delivery gate that prevents a passing internal catalog from
    # overclaiming a broken or ambiguous public release surface.
    publication = _run([
        sys.executable,
        str(ROOT / "scripts" / "verify_wp_009.py"),
        "--profile=static-pwa",
        "--delivery=cloudflare-static-web",
    ])
    if publication.returncode != 0:
        return _block(
            "public release eligibility gate failed",
            failed_package="WP-009",
            package_exit_code=publication.returncode,
        )

    identity_material = json.dumps(
        {
            "source_spec": SOURCE_SPEC,
            "catalog": [list(item) for item in CATALOG],
            "evidence": observed,
            "publication_gate": "pass",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    release_decision_id = "sha256:" + hashlib.sha256(identity_material).hexdigest()

    assembled = []
    by_element = {record["element_id"]: record for record in observed}
    for package, element, validator in CATALOG:
        record = by_element[element]
        assembled.append({
            "release_decision_id": release_decision_id,
            "package_id": package,
            "requirement_id": element,
            "validator": validator,
            "result": "pass",
            "evidence_refs": record["evidence_refs"],
        })

    print(json.dumps({
        "release_result": "pass",
        "source_spec": SOURCE_SPEC,
        "release_decision_id": release_decision_id,
        "catalog_validator_count": len(CATALOG),
        "passed_validator_count": len(assembled),
        "blocked_count": 0,
        "missing_evidence_count": 0,
        "publication_gate": "pass",
        "validator_evidence": assembled,
    }, sort_keys=True))
    print(f"Release verification passed: {len(assembled)}/{len(CATALOG)} validators; blocked=0; missing-evidence=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
