#!/usr/bin/env python3
"""AAT Mechanical Validator - Validates structural integrity (M1).

This module validates mechanical checks:
- M1a: JSON schema validation (strict mode: disallow unknown fields)
- M1b: Digest format validation (sha256:<64hex>)
- M1c: Required-fields-for-hashing check (no missing canonical fields)

All checks are deterministic with no network, LLM, or wall clock dependencies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import validators
except ImportError:
    jsonschema = None  # Will fail gracefully with clear error message


# Reason code for mechanical checks (NON_ADMISSIBLE severity)
REASON_M1_SCHEMA_INVALID = "AAT_M1_SCHEMA_INVALID"

# Digest format pattern
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

# Required canonical fields for each kernel object
REQUIRED_CANONICAL_FIELDS = {
    "input_manifest": ["input_manifest_version", "inputs"],
    "constraint_set_digest": ["csd_version", "constraints"],
    "constraint_acknowledgment_map": ["cam_version", "acknowledgments"],
    "method_binding": ["method_binding_version", "method_id", "action_kind"],
    "assumptions_unknowns_register": ["aur_version", "assumptions", "unknowns"],
    "claims_evidence_map": ["cem_version", "claims"],
    "admissibility_decision_record": [
        "adr_version",
        "action_kind",
        "decision",
        "enforcement_mode",
        "kernel_status",
        "profile_status",
        "reason_codes",
        "version_bindings",
    ],
}


def validate_mechanical(
    kernel_objects: dict[str, dict[str, Any]], schema_dir: Path
) -> list[str]:
    """Validate mechanical integrity M1 for all kernel objects.

    Args:
        kernel_objects: Dict mapping object names to their JSON content
        schema_dir: Path to directory containing JSON schemas

    Returns:
        List of reason codes (empty if all checks pass)
    """
    if jsonschema is None:
        # Graceful failure if jsonschema not installed
        return [REASON_M1_SCHEMA_INVALID]

    reason_codes = []

    # M1a: Schema validation
    if not _check_m1a_schema_validation(kernel_objects, schema_dir):
        return [REASON_M1_SCHEMA_INVALID]

    # M1b: Digest format validation
    if not _check_m1b_digest_format(kernel_objects):
        return [REASON_M1_SCHEMA_INVALID]

    # M1c: Required canonical fields
    if not _check_m1c_required_fields(kernel_objects):
        return [REASON_M1_SCHEMA_INVALID]

    return reason_codes


def _check_m1a_schema_validation(
    kernel_objects: dict[str, dict[str, Any]], schema_dir: Path
) -> bool:
    """M1a: Validate JSON schemas in strict mode (no additional properties).

    Args:
        kernel_objects: Dict mapping object names to their JSON content
        schema_dir: Path to directory containing JSON schemas

    Returns:
        True if all objects pass schema validation, False otherwise
    """
    schema_mapping = {
        "input_manifest": "aat_input_manifest_v0.json",
        "constraint_set_digest": "aat_constraint_set_digest_v0.json",
        "constraint_acknowledgment_map": "aat_constraint_acknowledgment_map_v0.json",
        "method_binding": "aat_method_binding_v0.json",
        "assumptions_unknowns_register": "aat_assumptions_unknowns_register_v0.json",
        "claims_evidence_map": "aat_claims_evidence_map_v0.json",
        "admissibility_decision_record": "aat_admissibility_decision_record_v0.json",
    }

    for obj_name, obj_data in kernel_objects.items():
        schema_file = schema_mapping.get(obj_name)
        if not schema_file:
            continue  # Skip unknown objects

        schema_path = schema_dir / schema_file
        if not schema_path.exists():
            return False  # Schema not found

        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.validate(instance=obj_data, schema=schema)
        except (jsonschema.ValidationError, json.JSONDecodeError):
            return False

    return True


def _check_m1b_digest_format(kernel_objects: dict[str, dict[str, Any]]) -> bool:
    """M1b: Validate digest format (sha256:<64hex>) for all digest fields.

    Args:
        kernel_objects: Dict mapping object names to their JSON content

    Returns:
        True if all digests match pattern, False otherwise
    """
    # Check IM inputs
    im = kernel_objects.get("input_manifest", {})
    for inp in im.get("inputs", []):
        digest = inp.get("digest", "")
        if digest and not DIGEST_PATTERN.match(digest):
            return False

    # Check CEM evidence refs
    cem = kernel_objects.get("claims_evidence_map", {})
    for claim in cem.get("claims", []):
        for evidence_ref in claim.get("evidence_refs", []):
            digest = evidence_ref.get("digest", "")
            if digest and not DIGEST_PATTERN.match(digest):
                return False

    # Check ADR version bindings
    adr = kernel_objects.get("admissibility_decision_record", {})
    version_bindings = adr.get("version_bindings", {})
    for binding_key in ["policy_digest", "validator_digest", "criteria_digest", "aat_suite_digest"]:
        digest = version_bindings.get(binding_key, "")
        if digest and not DIGEST_PATTERN.match(digest):
            return False

    return True


def _check_m1c_required_fields(kernel_objects: dict[str, dict[str, Any]]) -> bool:
    """M1c: Validate required canonical fields for hashing.

    Args:
        kernel_objects: Dict mapping object names to their JSON content

    Returns:
        True if all required fields present, False otherwise
    """
    for obj_name, required_fields in REQUIRED_CANONICAL_FIELDS.items():
        obj_data = kernel_objects.get(obj_name, {})
        if not obj_data:
            continue  # Object not provided (may be optional)

        for field in required_fields:
            if field not in obj_data:
                return False

    return True


def main() -> None:
    """CLI entry point for testing mechanical validator."""
    import sys

    if len(sys.argv) < 3:
        print("usage: aat_mechanical_validator.py <action_bundle_dir> <schema_dir>")
        sys.exit(1)

    bundle_dir = Path(sys.argv[1])
    schema_dir = Path(sys.argv[2])

    # Load kernel objects
    kernel_objects = {}
    for obj_name in REQUIRED_CANONICAL_FIELDS.keys():
        file_path = bundle_dir / f"{obj_name}.json"
        if file_path.exists():
            kernel_objects[obj_name] = json.loads(file_path.read_text())

    # Validate
    reason_codes = validate_mechanical(kernel_objects, schema_dir)

    if reason_codes:
        print(f"MECHANICAL_STATUS=FAIL")
        print(f"REASON_CODES={','.join(reason_codes)}")
        sys.exit(1)
    else:
        print(f"MECHANICAL_STATUS=PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
