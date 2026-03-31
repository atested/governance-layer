#!/usr/bin/env python3
"""AAT Kernel Validator - Validates universal invariants K1-K5.

This module validates the five kernel invariants that apply to all actions:
- K1: Phantom action detection (verification/test claims require tool_event evidence)
- K2: Undeclared dependency detection (all referenced artifacts must exist in IM)
- K3: Constraint acknowledgment completeness (every CSD constraint mapped in CAM)
- K4: Method binding required (MB.method_id must exist and be allowed)
- K5: Version binding required (ADR must have version binding digests)

All checks are deterministic with no network, LLM, or wall clock dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Reason codes for kernel invariants (HARD_STOP severity)
REASON_K1_PHANTOM_ACTION = "AAT_K1_PHANTOM_ACTION"
REASON_K2_UNDECLARED_DEPENDENCY = "AAT_K2_UNDECLARED_DEPENDENCY"
REASON_K3_CONSTRAINT_UNACKNOWLEDGED = "AAT_K3_CONSTRAINT_UNACKNOWLEDGED"
REASON_K4_METHOD_MISSING_OR_FORBIDDEN = "AAT_K4_METHOD_MISSING_OR_FORBIDDEN"
REASON_K5_VERSION_BINDING_MISSING = "AAT_K5_VERSION_BINDING_MISSING"

# Verification/test claim types that trigger K1 phantom action check
PHANTOM_CLAIM_TYPES = {"verification_completed", "test_passed", "test_failed"}

# Allowed methods for action kinds (v0 minimal - expand in v1)
ALLOWED_METHODS = {
    "CORE_GENERIC": {"generic_exec"},
    "TOOL_EXEC": {"tool_exec", "shell_exec", "bash_exec"},
    "FILE_OPERATION": {"file_read", "file_write", "file_delete"},
    "NETWORK_REQUEST": {"http_get", "http_post"},
    "MODEL_INVOKE": {"llm_call", "model_inference"},
}


def validate_kernel_invariants(
    input_manifest: dict[str, Any],
    constraint_set_digest: dict[str, Any],
    constraint_acknowledgment_map: dict[str, Any],
    method_binding: dict[str, Any],
    assumptions_unknowns_register: dict[str, Any],
    claims_evidence_map: dict[str, Any],
    admissibility_decision_record: dict[str, Any] | None = None,
) -> list[str]:
    """Validate all kernel invariants K1-K5.

    Args:
        input_manifest: IM object with inputs array
        constraint_set_digest: CSD object with constraints array
        constraint_acknowledgment_map: CAM object with acknowledgments array
        method_binding: MB object with method_id and action_kind
        assumptions_unknowns_register: AUR object (not used in K1-K5 but required for completeness)
        claims_evidence_map: CEM object with claims array
        admissibility_decision_record: Optional ADR for K5 validation

    Returns:
        List of reason codes (empty if all invariants pass)
    """
    reason_codes = []

    # K1: Phantom action detection
    reason_codes.extend(_check_k1_phantom_action(input_manifest, claims_evidence_map))

    # K2: Undeclared dependency detection
    reason_codes.extend(_check_k2_undeclared_dependency(claims_evidence_map, input_manifest))

    # K3: Constraint acknowledgment completeness
    reason_codes.extend(
        _check_k3_constraint_acknowledgment(constraint_set_digest, constraint_acknowledgment_map)
    )

    # K4: Method binding required
    reason_codes.extend(_check_k4_method_binding(method_binding))

    # K5: Version binding required (if ADR provided)
    if admissibility_decision_record is not None:
        reason_codes.extend(_check_k5_version_binding(admissibility_decision_record))

    return reason_codes


def _check_k1_phantom_action(
    input_manifest: dict[str, Any], claims_evidence_map: dict[str, Any]
) -> list[str]:
    """K1: Verification/test claims must have matching tool_event evidence refs in IM + CEM.

    Phantom actions are claims about verification or testing that lack concrete evidence.
    Every verification_completed, test_passed, or test_failed claim must reference
    at least one tool_event that exists in the input manifest.

    Args:
        input_manifest: IM with inputs array
        claims_evidence_map: CEM with claims array

    Returns:
        [REASON_K1_PHANTOM_ACTION] if phantom claim detected, else []
    """
    # Build set of tool_event digests from IM
    tool_event_digests = {
        inp["digest"] for inp in input_manifest.get("inputs", []) if inp.get("ref_type") == "tool_event"
    }

    # Check each claim
    for claim in claims_evidence_map.get("claims", []):
        claim_type = claim.get("claim_type", "")

        # Only check verification/test claims
        if claim_type not in PHANTOM_CLAIM_TYPES:
            continue

        # Get tool_event evidence refs for this claim
        evidence_refs = claim.get("evidence_refs", [])
        claim_tool_events = {
            ref["digest"] for ref in evidence_refs if ref.get("ref_type") == "tool_event"
        }

        # Phantom if no tool_event evidence OR evidence not in IM
        if not claim_tool_events:
            return [REASON_K1_PHANTOM_ACTION]

        # Check if any tool_event evidence exists in IM
        if not claim_tool_events.intersection(tool_event_digests):
            return [REASON_K1_PHANTOM_ACTION]

    return []


def _check_k2_undeclared_dependency(
    claims_evidence_map: dict[str, Any], input_manifest: dict[str, Any]
) -> list[str]:
    """K2: All evidence references must exist in input manifest.

    Every digest referenced in CEM evidence_refs must appear in IM inputs.
    This prevents undeclared dependencies.

    Args:
        claims_evidence_map: CEM with claims array
        input_manifest: IM with inputs array

    Returns:
        [REASON_K2_UNDECLARED_DEPENDENCY] if undeclared dependency detected, else []
    """
    # Build set of all input digests from IM
    input_digests = {inp["digest"] for inp in input_manifest.get("inputs", [])}

    # Check all evidence refs in CEM
    for claim in claims_evidence_map.get("claims", []):
        for evidence_ref in claim.get("evidence_refs", []):
            digest = evidence_ref.get("digest", "")
            if digest and digest not in input_digests:
                return [REASON_K2_UNDECLARED_DEPENDENCY]

    return []


def _check_k3_constraint_acknowledgment(
    constraint_set_digest: dict[str, Any], constraint_acknowledgment_map: dict[str, Any]
) -> list[str]:
    """K3: Every CSD constraint must be acknowledged in CAM.

    All constraints declared in the constraint set must have a corresponding
    acknowledgment (satisfied, not_applicable, blocked, or unknown).

    Args:
        constraint_set_digest: CSD with constraints array
        constraint_acknowledgment_map: CAM with acknowledgments array

    Returns:
        [REASON_K3_CONSTRAINT_UNACKNOWLEDGED] if unacknowledged constraint found, else []
    """
    # Build set of constraint IDs from CSD
    csd_constraint_ids = {
        constraint["constraint_id"] for constraint in constraint_set_digest.get("constraints", [])
    }

    # Build set of acknowledged constraint IDs from CAM
    cam_constraint_ids = {
        ack["constraint_id"] for ack in constraint_acknowledgment_map.get("acknowledgments", [])
    }

    # Check for unacknowledged constraints
    unacknowledged = csd_constraint_ids - cam_constraint_ids
    if unacknowledged:
        return [REASON_K3_CONSTRAINT_UNACKNOWLEDGED]

    return []


def _check_k4_method_binding(method_binding: dict[str, Any]) -> list[str]:
    """K4: Method binding must exist and be allowed for action kind.

    The method_id must be non-empty and must be in the allowed methods list
    for the declared action_kind.

    Args:
        method_binding: MB with method_id and action_kind

    Returns:
        [REASON_K4_METHOD_MISSING_OR_FORBIDDEN] if method invalid, else []
    """
    method_id = method_binding.get("method_id", "")
    action_kind = method_binding.get("action_kind", "")

    # Check method_id exists
    if not method_id:
        return [REASON_K4_METHOD_MISSING_OR_FORBIDDEN]

    # Check method_id is allowed for action_kind
    allowed = ALLOWED_METHODS.get(action_kind, set())
    if method_id not in allowed:
        return [REASON_K4_METHOD_MISSING_OR_FORBIDDEN]

    return []


def _check_k5_version_binding(admissibility_decision_record: dict[str, Any]) -> list[str]:
    """K5: Version bindings must be present in ADR.

    The ADR must contain all required version binding digests:
    - policy_digest
    - validator_digest
    - criteria_digest
    - aat_suite_digest

    Args:
        admissibility_decision_record: ADR with version_bindings

    Returns:
        [REASON_K5_VERSION_BINDING_MISSING] if any binding missing, else []
    """
    version_bindings = admissibility_decision_record.get("version_bindings", {})

    required_bindings = ["policy_digest", "validator_digest", "criteria_digest", "aat_suite_digest"]

    for binding in required_bindings:
        if not version_bindings.get(binding):
            return [REASON_K5_VERSION_BINDING_MISSING]

    return []


def main() -> None:
    """CLI entry point for testing kernel validator."""
    import sys

    if len(sys.argv) < 2:
        print("usage: aat_kernel_validator.py <action_bundle_dir>")
        sys.exit(1)

    bundle_dir = Path(sys.argv[1])

    # Load kernel objects
    im = json.loads((bundle_dir / "input_manifest.json").read_text())
    csd = json.loads((bundle_dir / "constraint_set_digest.json").read_text())
    cam = json.loads((bundle_dir / "constraint_acknowledgment_map.json").read_text())
    mb = json.loads((bundle_dir / "method_binding.json").read_text())
    aur = json.loads((bundle_dir / "assumptions_unknowns_register.json").read_text())
    cem = json.loads((bundle_dir / "claims_evidence_map.json").read_text())

    # Validate
    reason_codes = validate_kernel_invariants(im, csd, cam, mb, aur, cem)

    if reason_codes:
        print(f"KERNEL_STATUS=FAIL")
        print(f"REASON_CODES={','.join(reason_codes)}")
        sys.exit(1)
    else:
        print(f"KERNEL_STATUS=PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
