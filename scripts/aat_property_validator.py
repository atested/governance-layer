#!/usr/bin/env python3
"""AAT Property Validator - Validates idempotence and stability (P1-P2).

This module validates property tests:
- P1: Canonical idempotence (canonical(canonical(x)) == canonical(x))
- P2: Round-trip stability (deserialize(serialize(x)) == x for hashed objects)

All checks are deterministic with no network, LLM, or wall clock dependencies.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# Reason codes for property tests (NON_ADMISSIBLE severity)
REASON_P1_CANONICAL_IDEMPOTENCE_FAIL = "AAT_P1_CANONICAL_IDEMPOTENCE_FAIL"
REASON_P2_ROUND_TRIP_FAIL = "AAT_P2_ROUND_TRIP_FAIL"


def canonical_json(obj: Any) -> str:
    """Produce canonical JSON representation.

    Uses the same pattern as foundation_v0_process_ledger.py:
    - sorted keys
    - compact separators
    - ensure_ascii=False for UTF-8 support

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


def validate_property(kernel_objects: dict[str, dict[str, Any]]) -> list[str]:
    """Validate property tests P1-P2 for all kernel objects.

    Args:
        kernel_objects: Dict mapping object names to their JSON content

    Returns:
        List of reason codes (empty if all checks pass)
    """
    reason_codes = []

    # P1: Canonical idempotence
    if not _check_p1_canonical_idempotence(kernel_objects):
        reason_codes.append(REASON_P1_CANONICAL_IDEMPOTENCE_FAIL)

    # P2: Round-trip stability
    if not _check_p2_round_trip_stability(kernel_objects):
        reason_codes.append(REASON_P2_ROUND_TRIP_FAIL)

    return reason_codes


def _check_p1_canonical_idempotence(kernel_objects: dict[str, dict[str, Any]]) -> bool:
    """P1: Verify canonical(canonical(x)) == canonical(x).

    Canonical serialization must be idempotent - applying it twice
    should produce the same result as applying it once.

    Args:
        kernel_objects: Dict mapping object names to their JSON content

    Returns:
        True if idempotent for all objects, False otherwise
    """
    for obj_name, obj_data in kernel_objects.items():
        # First canonicalization
        canonical_once = canonical_json(obj_data)

        # Parse and canonicalize again
        try:
            parsed = json.loads(canonical_once)
            canonical_twice = canonical_json(parsed)
        except json.JSONDecodeError:
            return False

        # Must be identical
        if canonical_once != canonical_twice:
            return False

    return True


def _check_p2_round_trip_stability(kernel_objects: dict[str, dict[str, Any]]) -> bool:
    """P2: Verify deserialize(serialize(x)) == x for hashed objects.

    Objects used for hashing must survive a serialization round-trip
    without losing information or changing structure.

    Args:
        kernel_objects: Dict mapping object names to their JSON content

    Returns:
        True if stable for all objects, False otherwise
    """
    for obj_name, obj_data in kernel_objects.items():
        # Serialize to canonical JSON
        serialized = canonical_json(obj_data)

        # Deserialize back to object
        try:
            deserialized = json.loads(serialized)
        except json.JSONDecodeError:
            return False

        # Re-serialize to compare
        reserialized = canonical_json(deserialized)

        # Must match original serialization
        if serialized != reserialized:
            return False

        # Deep equality check on object structure
        if not _deep_equal(obj_data, deserialized):
            return False

    return True


def _deep_equal(obj1: Any, obj2: Any) -> bool:
    """Deep equality comparison for JSON objects.

    Args:
        obj1: First object
        obj2: Second object

    Returns:
        True if objects are deeply equal, False otherwise
    """
    if type(obj1) != type(obj2):
        return False

    if isinstance(obj1, dict):
        if set(obj1.keys()) != set(obj2.keys()):
            return False
        return all(_deep_equal(obj1[k], obj2[k]) for k in obj1.keys())

    if isinstance(obj1, list):
        if len(obj1) != len(obj2):
            return False
        return all(_deep_equal(obj1[i], obj2[i]) for i in range(len(obj1)))

    return obj1 == obj2


def main() -> None:
    """CLI entry point for testing property validator."""
    import sys

    if len(sys.argv) < 2:
        print("usage: aat_property_validator.py <action_bundle_dir>")
        sys.exit(1)

    bundle_dir = Path(sys.argv[1])

    # Load kernel objects
    kernel_objects = {}
    object_names = [
        "input_manifest",
        "constraint_set_digest",
        "constraint_acknowledgment_map",
        "method_binding",
        "assumptions_unknowns_register",
        "claims_evidence_map",
        "admissibility_decision_record",
    ]

    for obj_name in object_names:
        file_path = bundle_dir / f"{obj_name}.json"
        if file_path.exists():
            kernel_objects[obj_name] = json.loads(file_path.read_text())

    # Validate
    reason_codes = validate_property(kernel_objects)

    if reason_codes:
        print(f"PROPERTY_STATUS=FAIL")
        print(f"REASON_CODES={','.join(reason_codes)}")
        sys.exit(1)
    else:
        print(f"PROPERTY_STATUS=PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
