#!/usr/bin/env python3
"""AAT Main Orchestrator - Coordinates all validators and produces ADR.

This is the central entry point for Action Admissibility Testing (AAT).
It loads kernel objects from an action bundle, dispatches to validators,
aggregates results, and produces an Admissibility Decision Record (ADR).

Deterministic: Same inputs always produce same outputs (validated via two-run SHA256).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from aat_kernel_validator import validate_kernel_invariants
from aat_mechanical_validator import validate_mechanical
from aat_property_validator import validate_property
from aat_consistency_validator import validate_consistency
from aat_profile_registry import ProfileRegistry


# Decision outcomes
DECISION_PASS = "PASS"
DECISION_FAIL_NON_ADMISSIBLE = "FAIL_NON_ADMISSIBLE"
DECISION_FAIL_HARD_STOP = "FAIL_HARD_STOP"

# Kernel invariant codes (HARD_STOP severity)
KERNEL_CODES = {"K1", "K2", "K3", "K4", "K5"}

# Canonical reason code ordering: K* → M* → P* → C*
REASON_CODE_ORDER = {
    "K1": 1, "K2": 2, "K3": 3, "K4": 4, "K5": 5,
    "M1": 10,
    "P1": 20, "P2": 21,
    "C1": 30, "C2": 31, "C3": 32,
}


def canonical_json(obj: Any) -> str:
    """Produce canonical JSON representation.

    Args:
        obj: JSON-serializable object

    Returns:
        Canonical JSON string
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_canonical_json_obj(obj: Any) -> str:
    """Hash a canonical JSON object.

    Args:
        obj: JSON-serializable object

    Returns:
        sha256:<64hex> digest
    """
    canonical = canonical_json(obj)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_kernel_objects(bundle_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all kernel objects from action bundle directory.

    Args:
        bundle_dir: Path to action bundle directory

    Returns:
        Dict mapping object names to their JSON content

    Raises:
        FileNotFoundError: If required kernel objects missing
        json.JSONDecodeError: If JSON parsing fails
    """
    object_names = [
        "input_manifest",
        "constraint_set_digest",
        "constraint_acknowledgment_map",
        "method_binding",
        "assumptions_unknowns_register",
        "claims_evidence_map",
    ]

    kernel_objects = {}
    for obj_name in object_names:
        file_path = bundle_dir / f"{obj_name}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Missing kernel object: {file_path}")
        kernel_objects[obj_name] = json.loads(file_path.read_text())

    return kernel_objects


def extract_check_code(reason_code: str) -> str:
    """Extract check code from reason code.

    Args:
        reason_code: Full reason code (e.g., "AAT_K1_PHANTOM_ACTION")

    Returns:
        Check code (e.g., "K1")
    """
    # Format: AAT_<CHECK>_<DETAIL>
    # Extract the check part (K1, M1, P1, etc.)
    parts = reason_code.split("_")
    if len(parts) >= 2 and parts[0] == "AAT":
        return parts[1]
    return reason_code


def sort_reason_codes(reason_codes: list[str]) -> list[str]:
    """Sort reason codes in canonical order: K* → M* → P* → C*.

    Args:
        reason_codes: List of reason codes

    Returns:
        Sorted list of reason codes
    """
    def sort_key(code: str) -> tuple[int, str]:
        check_code = extract_check_code(code)
        order = REASON_CODE_ORDER.get(check_code, 999)
        return (order, code)

    return sorted(reason_codes, key=sort_key)


def compute_decision(
    kernel_reason_codes: list[str],
    profile_reason_codes: list[str],
    action_kind: str,
    registry: ProfileRegistry,
) -> tuple[str, str, str, list[str]]:
    """Compute final decision from reason codes.

    Args:
        kernel_reason_codes: Reason codes from kernel validator
        profile_reason_codes: Reason codes from profile validators (M1, P1-P2, C1-C3)
        action_kind: Action kind
        registry: Profile registry

    Returns:
        Tuple of (decision, kernel_status, profile_status, all_reason_codes)
    """
    # Filter reason codes by enforcement mode
    enforcing_checks = registry.get_enforcing_checks(action_kind)

    # Separate enforcing vs report-only
    enforcing_reason_codes = []
    report_only_reason_codes = []

    all_codes = kernel_reason_codes + profile_reason_codes
    for code in all_codes:
        check_code = extract_check_code(code)
        if check_code in enforcing_checks:
            enforcing_reason_codes.append(code)
        else:
            report_only_reason_codes.append(code)

    # Determine kernel status
    kernel_status = "FAIL" if kernel_reason_codes else "PASS"

    # Determine profile status (based on enforcing profile checks only)
    profile_enforcing_codes = [
        code for code in profile_reason_codes
        if extract_check_code(code) in enforcing_checks
    ]
    profile_status = "FAIL" if profile_enforcing_codes else "PASS"

    # Determine decision based on enforcing codes only
    has_kernel_failure = any(extract_check_code(c) in KERNEL_CODES for c in enforcing_reason_codes)

    if has_kernel_failure:
        decision = DECISION_FAIL_HARD_STOP
    elif enforcing_reason_codes:
        decision = DECISION_FAIL_NON_ADMISSIBLE
    else:
        decision = DECISION_PASS

    # Sort all reason codes canonically
    all_reason_codes = sort_reason_codes(enforcing_reason_codes + report_only_reason_codes)

    return decision, kernel_status, profile_status, all_reason_codes


def compute_version_bindings(bundle_dir: Path, repo_root: Path) -> dict[str, str]:
    """Compute version binding digests for ADR.

    Args:
        bundle_dir: Path to action bundle directory
        repo_root: Path to repository root

    Returns:
        Dict with policy_digest, validator_digest, criteria_digest, aat_suite_digest
    """
    # For v0, use placeholder digests (expand in production)
    # In production, these would be computed from actual policy/validator files
    placeholder = "sha256:" + ("0" * 64)

    return {
        "policy_digest": placeholder,
        "validator_digest": placeholder,
        "criteria_digest": placeholder,
        "aat_suite_digest": placeholder,
    }


def create_adr(
    decision: str,
    kernel_status: str,
    profile_status: str,
    reason_codes: list[str],
    action_kind: str,
    enforcement_mode: str,
    version_bindings: dict[str, str],
) -> dict[str, Any]:
    """Create Admissibility Decision Record (ADR).

    Args:
        decision: Overall decision (PASS, FAIL_NON_ADMISSIBLE, FAIL_HARD_STOP)
        kernel_status: Kernel validation status (PASS, FAIL)
        profile_status: Profile validation status (PASS, FAIL)
        reason_codes: Sorted list of reason codes
        action_kind: Action kind
        enforcement_mode: Enforcement mode (ENFORCING, REPORT_ONLY)
        version_bindings: Version binding digests

    Returns:
        ADR object following canonical field order
    """
    # Use canonical field order from schema
    adr = {
        "adr_version": "v0",
        "action_kind": action_kind,
        "decision": decision,
        "enforcement_mode": enforcement_mode,
        "kernel_status": kernel_status,
        "profile_status": profile_status,
        "reason_codes": reason_codes,
        "version_bindings": version_bindings,
    }

    return adr


def main() -> int:
    """Main entry point for AAT validation.

    Returns:
        Exit code (0=PASS, 1=NON_ADMISSIBLE, 2=HARD_STOP)
    """
    parser = argparse.ArgumentParser(description="AAT Main Orchestrator")
    parser.add_argument("--bundle-dir", required=True, help="Action bundle directory")
    parser.add_argument("--schema-dir", help="Schema directory (default: system/schemas)")
    parser.add_argument("--repo-root", help="Repository root (default: current directory)")
    parser.add_argument("--output", help="Output ADR file path")
    parser.add_argument(
        "--profile",
        help="Explicit profile override (default: method_binding.action_kind, fallback CORE_GENERIC)",
    )
    parser.add_argument(
        "--enforcement-mode",
        choices=["ENFORCING", "REPORT_ONLY"],
        default="ENFORCING",
        help="Enforcement mode (default: ENFORCING)",
    )

    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir)
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    schema_dir = Path(args.schema_dir) if args.schema_dir else repo_root / "system/schemas"

    try:
        # Load kernel objects
        kernel_objects = load_kernel_objects(bundle_dir)

        # Initialize profile registry
        registry = ProfileRegistry()

        # Resolve profile deterministically:
        # CLI --profile takes precedence, then method_binding.action_kind, then CORE_GENERIC.
        selected_profile = args.profile or kernel_objects["method_binding"].get(
            "action_kind", "CORE_GENERIC"
        )
        if not registry.has_profile(selected_profile):
            print(f"ERROR: unknown profile={selected_profile}", file=sys.stderr)
            return 2

        # Run kernel validator (K1-K5)
        kernel_reason_codes = validate_kernel_invariants(
            kernel_objects["input_manifest"],
            kernel_objects["constraint_set_digest"],
            kernel_objects["constraint_acknowledgment_map"],
            kernel_objects["method_binding"],
            kernel_objects["assumptions_unknowns_register"],
            kernel_objects["claims_evidence_map"],
        )

        # Run mechanical validator (M1)
        mechanical_reason_codes = validate_mechanical(kernel_objects, schema_dir)

        # Run property validator (P1-P2)
        property_reason_codes = validate_property(kernel_objects)

        # Run consistency validator (C1-C3)
        consistency_reason_codes = validate_consistency(
            kernel_objects["input_manifest"],
            kernel_objects["constraint_acknowledgment_map"],
            kernel_objects["claims_evidence_map"],
        )

        # Aggregate profile reason codes
        profile_reason_codes = (
            mechanical_reason_codes + property_reason_codes + consistency_reason_codes
        )

        # Compute decision
        decision, kernel_status, profile_status, all_reason_codes = compute_decision(
            kernel_reason_codes, profile_reason_codes, selected_profile, registry
        )

        # Compute version bindings
        version_bindings = compute_version_bindings(bundle_dir, repo_root)

        # Create ADR
        adr = create_adr(
            decision,
            kernel_status,
            profile_status,
            all_reason_codes,
            selected_profile,
            args.enforcement_mode,
            version_bindings,
        )

        # Output ADR
        adr_json = canonical_json(adr)
        if args.output:
            Path(args.output).write_text(adr_json)
        else:
            print(adr_json)

        # Print summary to stderr
        print(f"DECISION={decision}", file=sys.stderr)
        print(f"KERNEL_STATUS={kernel_status}", file=sys.stderr)
        print(f"PROFILE_STATUS={profile_status}", file=sys.stderr)
        if all_reason_codes:
            print(f"REASON_CODES={','.join(all_reason_codes)}", file=sys.stderr)

        # Exit code based on decision
        if decision == DECISION_PASS:
            return 0
        elif decision == DECISION_FAIL_NON_ADMISSIBLE:
            return 1
        else:  # DECISION_FAIL_HARD_STOP
            return 2

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
