#!/usr/bin/env python3
"""
event_model.py — Event model extension for governed-action baseline.

Provides:
  1. Compound metadata schema and validation for governed action records.
  2. Non-action governance event types (verification_state_transition,
     opaque_artifact_approval, opaque_artifact_revocation,
     opaque_invocation_decision) that participate in the decision chain.
  3. Construction and validation helpers used by verify-record, verify-chain,
     and replay-record.

Design constraints (per GOVERNED_ACTION_BASELINE_SPEC v1.1):
  - Compound metadata is optional.  Standalone steps carry none.
  - When present, compound_metadata contains compound_action_id and depends_on.
  - Each depends_on entry is {step_id, dependency_type}.
  - dependency_type in {"data", "state", "control"}.
  - Non-action events are first-class chain material with the same
    tamper-evidence and ordering guarantees as action records.
  - Non-action events are chain-valid but not policy-replayable.
  - governed_family is an opaque string identifier at baseline.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
import uuid


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_MODEL_VERSION = "0.1"

NON_ACTION_EVENT_TYPES = frozenset([
    "verification_state_transition",
    "opaque_artifact_approval",
    "opaque_artifact_revocation",
    "opaque_invocation_decision",
    "usage_attestation",
    "ungoverned_operation_observed",
    "registry_config_change",
    "help_query",
    "feedback_submitted",
    "telemetry_submitted",
    "telemetry_opt_in_changed",
    "notification_received",
    "notification_dismissed",
    "notifications_viewed",
    "disclosure_shown",
    "questionnaire_response",
    "capacity_inputs",
    "case_document_generated",
])

UNGOVERNED_OPERATION_TYPES = frozenset([
    "read", "write", "edit", "delete", "move", "execute",
    "glob", "grep", "list", "other",
])

ALLOWED_DEPENDENCY_TYPES = frozenset(["data", "state", "control"])

VERIFICATION_STATES = frozenset(["unverified", "verified", "drift_detected"])

OPAQUE_INVOCATION_RESOLUTIONS = frozenset([
    "approved_lookup",
    "transparent_restatement",
    "operator_intervention",
    "denied",
])


# ---------------------------------------------------------------------------
# Canonical JSON helpers  (match policy-eval / verify-record conventions)
# ---------------------------------------------------------------------------

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Compound metadata validation
# ---------------------------------------------------------------------------

def validate_compound_metadata(meta: dict) -> tuple[bool, Optional[str]]:
    """Validate compound_metadata dict.

    Returns (ok, error_message).
    """
    if not isinstance(meta, dict):
        return False, "compound_metadata must be an object"

    compound_action_id = meta.get("compound_action_id")
    if not isinstance(compound_action_id, str) or not compound_action_id:
        return False, "compound_metadata.compound_action_id must be a non-empty string"

    depends_on = meta.get("depends_on")
    if not isinstance(depends_on, list):
        return False, "compound_metadata.depends_on must be a list"

    if len(depends_on) == 0:
        return False, "compound_metadata.depends_on must contain at least one dependency"

    seen_step_ids = set()
    for i, dep in enumerate(depends_on):
        if not isinstance(dep, dict):
            return False, f"compound_metadata.depends_on[{i}] must be an object"

        step_id = dep.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            return False, f"compound_metadata.depends_on[{i}].step_id must be a non-empty string"

        dep_type = dep.get("dependency_type")
        if dep_type not in ALLOWED_DEPENDENCY_TYPES:
            return False, (
                f"compound_metadata.depends_on[{i}].dependency_type must be "
                f"one of {sorted(ALLOWED_DEPENDENCY_TYPES)}, got: {dep_type!r}"
            )

        dep_key = (step_id, dep_type)
        if dep_key in seen_step_ids:
            return False, (
                f"compound_metadata.depends_on[{i}]: duplicate dependency "
                f"(step_id={step_id!r}, dependency_type={dep_type!r})"
            )
        seen_step_ids.add(dep_key)

        # Only step_id and dependency_type are recognized at baseline.
        extra_keys = set(dep.keys()) - {"step_id", "dependency_type"}
        if extra_keys:
            return False, (
                f"compound_metadata.depends_on[{i}]: unrecognized keys: {sorted(extra_keys)}"
            )

    # Only compound_action_id and depends_on are recognized at baseline.
    extra_keys = set(meta.keys()) - {"compound_action_id", "depends_on"}
    if extra_keys:
        return False, f"compound_metadata: unrecognized keys: {sorted(extra_keys)}"

    return True, None


# ---------------------------------------------------------------------------
# Non-action event validation
# ---------------------------------------------------------------------------

def _validate_verification_state_transition(event: dict) -> tuple[bool, Optional[str]]:
    governed_family = event.get("governed_family")
    if not isinstance(governed_family, str) or not governed_family:
        return False, "verification_state_transition: governed_family must be a non-empty string"

    from_state = event.get("from_state")
    to_state = event.get("to_state")
    for label, val in [("from_state", from_state), ("to_state", to_state)]:
        if val not in VERIFICATION_STATES:
            return False, (
                f"verification_state_transition: {label} must be one of "
                f"{sorted(VERIFICATION_STATES)}, got: {val!r}"
            )

    if from_state == to_state:
        return False, "verification_state_transition: from_state and to_state must differ"

    return True, None


def _validate_opaque_artifact_approval(event: dict) -> tuple[bool, Optional[str]]:
    artifact_identity = event.get("artifact_identity")
    if not isinstance(artifact_identity, str) or not artifact_identity:
        return False, "opaque_artifact_approval: artifact_identity must be a non-empty string"

    approving_operator = event.get("approving_operator")
    if not isinstance(approving_operator, str) or not approving_operator:
        return False, "opaque_artifact_approval: approving_operator must be a non-empty string"

    governed_family = event.get("governed_family")
    if not isinstance(governed_family, str) or not governed_family:
        return False, "opaque_artifact_approval: governed_family must be a non-empty string"

    deployment_context = event.get("deployment_context")
    if not isinstance(deployment_context, str) or not deployment_context:
        return False, "opaque_artifact_approval: deployment_context must be a non-empty string"

    policy_version = event.get("policy_version")
    if not isinstance(policy_version, str) or not policy_version:
        return False, "opaque_artifact_approval: policy_version must be a non-empty string"

    return True, None


def _validate_opaque_artifact_revocation(event: dict) -> tuple[bool, Optional[str]]:
    # Same required fields as approval.
    artifact_identity = event.get("artifact_identity")
    if not isinstance(artifact_identity, str) or not artifact_identity:
        return False, "opaque_artifact_revocation: artifact_identity must be a non-empty string"

    revoking_operator = event.get("revoking_operator")
    if not isinstance(revoking_operator, str) or not revoking_operator:
        return False, "opaque_artifact_revocation: revoking_operator must be a non-empty string"

    governed_family = event.get("governed_family")
    if not isinstance(governed_family, str) or not governed_family:
        return False, "opaque_artifact_revocation: governed_family must be a non-empty string"

    deployment_context = event.get("deployment_context")
    if not isinstance(deployment_context, str) or not deployment_context:
        return False, "opaque_artifact_revocation: deployment_context must be a non-empty string"

    policy_version = event.get("policy_version")
    if not isinstance(policy_version, str) or not policy_version:
        return False, "opaque_artifact_revocation: policy_version must be a non-empty string"

    return True, None


def _validate_opaque_invocation_decision(event: dict) -> tuple[bool, Optional[str]]:
    artifact_identity = event.get("artifact_identity")
    if not isinstance(artifact_identity, str) or not artifact_identity:
        return False, "opaque_invocation_decision: artifact_identity must be a non-empty string"

    governed_family = event.get("governed_family")
    if not isinstance(governed_family, str) or not governed_family:
        return False, "opaque_invocation_decision: governed_family must be a non-empty string"

    resolution = event.get("resolution")
    if resolution not in OPAQUE_INVOCATION_RESOLUTIONS:
        return False, (
            f"opaque_invocation_decision: resolution must be one of "
            f"{sorted(OPAQUE_INVOCATION_RESOLUTIONS)}, got: {resolution!r}"
        )

    return True, None


def _validate_ungoverned_operation_observed(event: dict) -> tuple[bool, Optional[str]]:
    op_type = event.get("operation_type")
    if not isinstance(op_type, str) or not op_type:
        return False, "ungoverned_operation_observed: operation_type must be a non-empty string"
    if op_type not in UNGOVERNED_OPERATION_TYPES:
        return False, (
            f"ungoverned_operation_observed: operation_type must be one of "
            f"{sorted(UNGOVERNED_OPERATION_TYPES)}, got: {op_type!r}"
        )
    # target is optional
    target = event.get("target")
    if target is not None and not isinstance(target, str):
        return False, "ungoverned_operation_observed: target must be a string or null"
    # source is optional (identifies the reporting tool)
    source = event.get("source")
    if source is not None and not isinstance(source, str):
        return False, "ungoverned_operation_observed: source must be a string or null"
    return True, None


_EVENT_TYPE_VALIDATORS = {
    "verification_state_transition": _validate_verification_state_transition,
    "opaque_artifact_approval": _validate_opaque_artifact_approval,
    "opaque_artifact_revocation": _validate_opaque_artifact_revocation,
    "opaque_invocation_decision": _validate_opaque_invocation_decision,
    "ungoverned_operation_observed": _validate_ungoverned_operation_observed,
}


def validate_non_action_event(event: dict) -> tuple[bool, Optional[str]]:
    """Validate a non-action governance event record.

    Returns (ok, error_message).
    """
    event_type = event.get("event_type")
    if event_type not in NON_ACTION_EVENT_TYPES:
        return False, f"event_type must be one of {sorted(NON_ACTION_EVENT_TYPES)}, got: {event_type!r}"

    # Common required fields.
    timestamp = event.get("timestamp_utc")
    if not isinstance(timestamp, str) or not timestamp:
        return False, "timestamp_utc must be a non-empty string"

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return False, "event_id must be a non-empty string"

    record_hash = event.get("record_hash")
    if not isinstance(record_hash, str) or not record_hash.startswith("sha256:"):
        return False, "record_hash must be a sha256-prefixed string"

    # Type-specific validation.
    validator = _EVENT_TYPE_VALIDATORS.get(event_type)
    if validator:
        ok, err = validator(event)
        if not ok:
            return False, err

    # Compound metadata is optional on non-action events too.
    compound_meta = event.get("compound_metadata")
    if compound_meta is not None:
        ok, err = validate_compound_metadata(compound_meta)
        if not ok:
            return False, err

    return True, None


def is_non_action_event(record: dict) -> bool:
    """Return True if the record is a non-action governance event."""
    return record.get("event_type") in NON_ACTION_EVENT_TYPES


# ---------------------------------------------------------------------------
# Non-action event construction
# ---------------------------------------------------------------------------

def _compute_event_record_hash(event: dict) -> str:
    """Compute record_hash for a non-action event.

    Uses the same canonical JSON convention as action records:
    set record_hash to None, serialize canonically, SHA-256.
    """
    copy = dict(event)
    copy["record_hash"] = None
    preimage = canonical_json(copy)
    return "sha256:" + sha256_hex(preimage)


def build_non_action_event(
    event_type: str,
    payload: dict,
    prev_record_hash: Optional[str] = None,
    compound_metadata: Optional[dict] = None,
) -> dict:
    """Build a non-action governance event record.

    payload contains the type-specific fields (e.g. governed_family,
    from_state, to_state for verification_state_transition).
    """
    if event_type not in NON_ACTION_EVENT_TYPES:
        raise ValueError(f"unknown non-action event_type: {event_type}")

    event = {
        "event_model_version": EVENT_MODEL_VERSION,
        "event_type": event_type,
        "event_id": str(uuid.uuid4()),
        "timestamp_utc": now_utc_z(),
        "prev_record_hash": prev_record_hash,
        "record_hash": None,
    }
    event.update(payload)

    if compound_metadata is not None:
        event["compound_metadata"] = compound_metadata

    event["record_hash"] = _compute_event_record_hash(event)
    return event


# ---------------------------------------------------------------------------
# Hash verification for non-action events
# ---------------------------------------------------------------------------

def verify_non_action_event_hash(event: dict) -> tuple[bool, Optional[str]]:
    """Verify that the record_hash of a non-action event is correct."""
    stored = event.get("record_hash")
    if not isinstance(stored, str) or not stored.startswith("sha256:"):
        return False, "record_hash missing or invalid"

    recomputed = _compute_event_record_hash(event)
    if recomputed != stored:
        return False, f"record_hash mismatch (expected={stored}, computed={recomputed})"

    return True, None
