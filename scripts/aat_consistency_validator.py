#!/usr/bin/env python3
"""AAT Consistency Validator - Validates governance consistency (C1-C3).

This module validates consistency checks:
- C1: Contradiction detection (constraint both satisfied and unknown)
- C2: Evidence reference integrity (CEM refs must exist in IM AND ref_type allowed for claim_type)
- C3: Forbidden claim detection (verification patterns without evidence mapping)

All checks are deterministic with no network, LLM, or wall clock dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Reason codes for consistency checks (NON_ADMISSIBLE severity)
REASON_C1_CONTRADICTION_DETECTED = "AAT_C1_CONTRADICTION_DETECTED"
REASON_C2_EVIDENCE_REF_NOT_IN_IM = "AAT_C2_EVIDENCE_REF_NOT_IN_IM"
REASON_C3_FORBIDDEN_CLAIM_NO_EVIDENCE = "AAT_C3_FORBIDDEN_CLAIM_NO_EVIDENCE"

# Allowed evidence ref_types for each claim_type
ALLOWED_EVIDENCE_REFS = {
    "verification_completed": {"tool_event", "file_digest", "proof_artifact"},
    "test_passed": {"tool_event", "file_digest", "proof_artifact"},
    "test_failed": {"tool_event", "file_digest", "proof_artifact"},
    "analysis_completed": {"file_digest", "retrieved_content", "proof_artifact"},
    "review_completed": {"file_digest", "retrieved_content", "proof_artifact"},
}

# Claim types that require evidence (forbidden without evidence)
FORBIDDEN_CLAIM_TYPES_WITHOUT_EVIDENCE = {
    "verification_completed",
    "test_passed",
    "test_failed",
}


def validate_consistency(
    input_manifest: dict[str, Any],
    constraint_acknowledgment_map: dict[str, Any],
    claims_evidence_map: dict[str, Any],
) -> list[str]:
    """Validate consistency C1-C3 for kernel objects.

    Args:
        input_manifest: IM with inputs array
        constraint_acknowledgment_map: CAM with acknowledgments array
        claims_evidence_map: CEM with claims array

    Returns:
        List of reason codes (empty if all checks pass)
    """
    reason_codes = []

    # C1: Contradiction detection
    if not _check_c1_no_contradictions(constraint_acknowledgment_map):
        reason_codes.append(REASON_C1_CONTRADICTION_DETECTED)

    # C2: Evidence reference integrity
    if not _check_c2_evidence_ref_integrity(input_manifest, claims_evidence_map):
        reason_codes.append(REASON_C2_EVIDENCE_REF_NOT_IN_IM)

    # C3: Forbidden claim detection
    if not _check_c3_no_forbidden_claims(claims_evidence_map):
        reason_codes.append(REASON_C3_FORBIDDEN_CLAIM_NO_EVIDENCE)

    return reason_codes


def _check_c1_no_contradictions(constraint_acknowledgment_map: dict[str, Any]) -> bool:
    """C1: Detect logical contradictions in constraint acknowledgments.

    A constraint cannot be both satisfied and unknown, or both not_applicable
    and blocked. This check prevents contradictory acknowledgment states.

    Note: In v0, we only have one acknowledgment per constraint_id, so we check
    for the contradiction case where the same constraint appears multiple times
    with conflicting statuses.

    Args:
        constraint_acknowledgment_map: CAM with acknowledgments array

    Returns:
        True if no contradictions, False if contradiction detected
    """
    # Build map of constraint_id -> status
    constraint_status = {}
    for ack in constraint_acknowledgment_map.get("acknowledgments", []):
        constraint_id = ack.get("constraint_id", "")
        status = ack.get("status", "")

        if constraint_id in constraint_status:
            # Duplicate acknowledgment for same constraint
            existing_status = constraint_status[constraint_id]

            # Check for contradictory states
            if _are_statuses_contradictory(existing_status, status):
                return False

        constraint_status[constraint_id] = status

    return True


def _are_statuses_contradictory(status1: str, status2: str) -> bool:
    """Check if two acknowledgment statuses are contradictory.

    Args:
        status1: First status
        status2: Second status

    Returns:
        True if contradictory, False otherwise
    """
    contradictions = [
        ("satisfied", "unknown"),
        ("satisfied", "blocked"),
        ("not_applicable", "blocked"),
        ("not_applicable", "satisfied"),
    ]

    for s1, s2 in contradictions:
        if (status1 == s1 and status2 == s2) or (status1 == s2 and status2 == s1):
            return True

    return False


def _check_c2_evidence_ref_integrity(
    input_manifest: dict[str, Any], claims_evidence_map: dict[str, Any]
) -> bool:
    """C2: Evidence refs in CEM must exist in IM and have allowed ref_type.

    Every evidence reference must:
    1. Exist in the input manifest
    2. Have a ref_type that is allowed for the claim_type

    Args:
        input_manifest: IM with inputs array
        claims_evidence_map: CEM with claims array

    Returns:
        True if all evidence refs valid, False otherwise
    """
    # Build map of digest -> ref_type from IM
    input_refs = {inp["digest"]: inp["ref_type"] for inp in input_manifest.get("inputs", [])}

    # Check each claim's evidence refs
    for claim in claims_evidence_map.get("claims", []):
        claim_type = claim.get("claim_type", "")
        allowed_ref_types = ALLOWED_EVIDENCE_REFS.get(claim_type, set())

        for evidence_ref in claim.get("evidence_refs", []):
            digest = evidence_ref.get("digest", "")
            ref_type = evidence_ref.get("ref_type", "")

            # Evidence must exist in IM
            if digest not in input_refs:
                return False

            # ref_type must be allowed for claim_type
            if ref_type not in allowed_ref_types:
                return False

            # ref_type in evidence_ref must match ref_type in IM
            if input_refs[digest] != ref_type:
                return False

    return True


def _check_c3_no_forbidden_claims(claims_evidence_map: dict[str, Any]) -> bool:
    """C3: Verification claims must have evidence mapping.

    Verification, test_passed, and test_failed claims are forbidden
    without at least one evidence reference.

    Args:
        claims_evidence_map: CEM with claims array

    Returns:
        True if no forbidden claims, False if forbidden claim detected
    """
    for claim in claims_evidence_map.get("claims", []):
        claim_type = claim.get("claim_type", "")

        # Skip non-forbidden claim types
        if claim_type not in FORBIDDEN_CLAIM_TYPES_WITHOUT_EVIDENCE:
            continue

        # Forbidden claim type must have evidence
        evidence_refs = claim.get("evidence_refs", [])
        if not evidence_refs:
            return False

    return True


def main() -> None:
    """CLI entry point for testing consistency validator."""
    import sys

    if len(sys.argv) < 2:
        print("usage: aat_consistency_validator.py <action_bundle_dir>")
        sys.exit(1)

    bundle_dir = Path(sys.argv[1])

    # Load kernel objects
    im = json.loads((bundle_dir / "input_manifest.json").read_text())
    cam = json.loads((bundle_dir / "constraint_acknowledgment_map.json").read_text())
    cem = json.loads((bundle_dir / "claims_evidence_map.json").read_text())

    # Validate
    reason_codes = validate_consistency(im, cam, cem)

    if reason_codes:
        print(f"CONSISTENCY_STATUS=FAIL")
        print(f"REASON_CODES={','.join(reason_codes)}")
        sys.exit(1)
    else:
        print(f"CONSISTENCY_STATUS=PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
