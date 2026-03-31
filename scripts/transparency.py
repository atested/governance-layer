#!/usr/bin/env python3
"""
transparency.py — Transparency classification and opaque path handling.

Implements the governed-action baseline spec v1.1 §6 transparency check,
§8 opaque invocation model, and §9.1 artifact identity computation.

Flow (spec §6):
  Action arrives → Classification → Dependency check → Transparency check
    ├─ Transparent → policy-eval fast path (§6.1, §8.2)
    └─ Opaque → identity check → approval lookup → restatement → friction (§8.3)

Design constraints:
  - Transparent actions pass through with zero added friction.
  - Opaque actions follow the full slow path per §8.3.
  - Artifact identity is SHA-256 of byte content, lowercase hex (§9.1).
  - Approval scope is conjunctive across 5 fields (§9.4).
  - Transparent restatement is stubbed as not-possible at baseline (§8.4).
  - No path/origin-based exceptions for unverified opaque artifacts (§8.5).
  - governed_family is an opaque string identifier at baseline.
"""

import hashlib
from typing import Optional

from event_model import build_non_action_event


# ---------------------------------------------------------------------------
# Transparency classification (§8.1)
# ---------------------------------------------------------------------------

def classify_transparency(tool: str, capability_class: str, registry: dict) -> str:
    """Classify an action as 'transparent' or 'opaque'.

    At baseline, classification is determined by the capability registry:
    - Tools registered in the capability registry with known semantics
      are transparent — their semantics are visible at the invocation boundary.
    - Actions whose tool is not in the registry, or whose registry entry
      marks content_visible_to_evaluator=False and the action carries an
      opaque executable artifact, are opaque.

    For the baseline, the heuristic is:
    - If the tool is in the registry and the evaluator can see the content,
      the action is transparent.
    - Otherwise it is opaque.

    This function does not inspect artifact bytes — it classifies based on
    the tool's registry declaration.
    """
    tools = registry.get("tools", [])
    for entry in tools:
        if entry.get("tool") == tool or entry.get("capability_class") == capability_class:
            # If the registry entry explicitly marks content as not visible
            # to the evaluator, this is an opaque-capable tool. However,
            # at baseline only actions that carry an opaque_artifact_path
            # or opaque_executable field are routed to the opaque path.
            # The classify function is called with additional context by
            # classify_action_transparency below.
            return "transparent"
    return "opaque"


def classify_action_transparency(
    request: dict,
    registry: dict,
) -> str:
    """Classify a governance action request as 'transparent' or 'opaque'.

    An action is opaque if:
    1. Its tool is not registered in the capability registry, OR
    2. The request carries an opaque_artifact_path or opaque_executable
       field, indicating an invocation whose semantics are not visible
       at the governance boundary.

    Otherwise the action is transparent.
    """
    tool = request.get("tool", "")
    capability_class = request.get("capability_class", tool)
    args = request.get("args", {})

    # Check for explicit opaque artifact markers.
    if args.get("opaque_artifact_path") or args.get("opaque_executable"):
        return "opaque"

    return classify_transparency(tool, capability_class, registry)


# ---------------------------------------------------------------------------
# Artifact identity (§9.1)
# ---------------------------------------------------------------------------

def compute_artifact_identity(artifact_bytes: bytes) -> str:
    """Compute content-derived identity for an opaque artifact.

    Returns SHA-256 lowercase hex digest (no prefix) per spec §9.1.
    """
    return hashlib.sha256(artifact_bytes).hexdigest()


def compute_artifact_identity_prefixed(artifact_bytes: bytes) -> str:
    """Compute content-derived identity with sha256: prefix."""
    return "sha256:" + compute_artifact_identity(artifact_bytes)


# ---------------------------------------------------------------------------
# Transparent restatement hook (§8.4)
# ---------------------------------------------------------------------------

def attempt_transparent_restatement(
    request: dict,
    artifact_identity: str,
    governed_family: str,
) -> dict:
    """Attempt transparent restatement of an opaque invocation.

    At baseline, restatement always returns not-possible.
    The interface is defined so that future family-specific
    implementations can override this behavior.

    Returns:
        {
            "possible": False,
            "reason": "baseline: transparent restatement not implemented",
        }
    """
    return {
        "possible": False,
        "reason": "baseline: transparent restatement not implemented",
    }


# ---------------------------------------------------------------------------
# Opaque path handler (§8.3)
# ---------------------------------------------------------------------------

def handle_opaque_action(
    request: dict,
    artifact_bytes: bytes,
    governed_family: str,
    deployment_context: str,
    policy_version: str,
    approval_lookup_fn,
    prev_record_hash: Optional[str] = None,
    compound_metadata: Optional[dict] = None,
) -> dict:
    """Handle an opaque action through the full slow path per spec §8.3.

    Steps:
    1. Compute content-derived artifact identity (§9.1)
    2. Approval lookup (§9.4) — conjunctive scope match
    3. If approved → record opaque_invocation_decision(approved_lookup)
    4. If not approved → attempt transparent restatement (§8.4)
    5. If restatement possible → return restatement result
    6. If not → friction path, record opaque_invocation_decision

    Args:
        request: The original action request dict.
        artifact_bytes: Raw bytes of the opaque artifact.
        governed_family: Opaque string identifier for the governed family.
        deployment_context: Deployment/host environment identifier.
        policy_version: Policy version identifier.
        approval_lookup_fn: Callable(artifact_identity, governed_family,
                           deployment_context, policy_version) → approval_record or None.
        prev_record_hash: Previous record hash for chain linking.
        compound_metadata: Optional compound metadata for the event.

    Returns:
        {
            "resolution": str,  # approved_lookup | transparent_restatement | operator_intervention | denied
            "artifact_identity": str,
            "approved": bool,
            "event": dict,  # the opaque_invocation_decision event
            "restatement": dict | None,  # restatement result if attempted
            "approval_record": dict | None,  # approval record if found
        }
    """
    # Step 1: Identity check (§9.1).
    artifact_identity = compute_artifact_identity_prefixed(artifact_bytes)

    # Step 2: Approval lookup (§9.4).
    approval_record = approval_lookup_fn(
        artifact_identity,
        governed_family,
        deployment_context,
        policy_version,
    )

    if approval_record is not None:
        # Approved opaque path.
        event = build_non_action_event(
            "opaque_invocation_decision",
            {
                "artifact_identity": artifact_identity,
                "governed_family": governed_family,
                "resolution": "approved_lookup",
            },
            prev_record_hash=prev_record_hash,
            compound_metadata=compound_metadata,
        )
        return {
            "resolution": "approved_lookup",
            "artifact_identity": artifact_identity,
            "approved": True,
            "event": event,
            "restatement": None,
            "approval_record": approval_record,
        }

    # Step 3: Unapproved — attempt transparent restatement (§8.4).
    restatement = attempt_transparent_restatement(
        request, artifact_identity, governed_family,
    )

    if restatement.get("possible"):
        event = build_non_action_event(
            "opaque_invocation_decision",
            {
                "artifact_identity": artifact_identity,
                "governed_family": governed_family,
                "resolution": "transparent_restatement",
            },
            prev_record_hash=prev_record_hash,
            compound_metadata=compound_metadata,
        )
        return {
            "resolution": "transparent_restatement",
            "artifact_identity": artifact_identity,
            "approved": False,
            "event": event,
            "restatement": restatement,
            "approval_record": None,
        }

    # Step 4: Friction path — operator decision required (§8.3).
    # At baseline, without operator UX, this results in denial.
    event = build_non_action_event(
        "opaque_invocation_decision",
        {
            "artifact_identity": artifact_identity,
            "governed_family": governed_family,
            "resolution": "denied",
        },
        prev_record_hash=prev_record_hash,
        compound_metadata=compound_metadata,
    )
    return {
        "resolution": "denied",
        "artifact_identity": artifact_identity,
        "approved": False,
        "event": event,
        "restatement": restatement,
        "approval_record": None,
    }
