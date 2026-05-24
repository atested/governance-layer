#!/usr/bin/env python3
"""
approval_store.py — Minimal approval lookup for opaque artifact identities.

Implements the approved artifact identity store (spec §9.7) as a derived
index over approval and revocation events. The store is not an independent
authority — it must be consistent with the approval event history.

Approval scope (spec §9.4) is the conjunction of five fields:
  - artifact_identity: SHA-256 content hash of the artifact
  - approving_operator: operator who granted approval
  - governed_family: governed family/surface identifier
  - deployment_context: deployment/host environment
  - policy_version: policy/baseline version in effect

An approval applies only when all five fields match the current context.
Revocations remove approvals by matching artifact_identity +
governed_family + deployment_context + policy_version.

Scope mismatch is automatic — if any field doesn't match, the approval
simply doesn't apply (spec §9.5).

Signature verification (F-11): When require_signatures=True, approval and
revocation events must carry a valid Ed25519 signature. Events without a
signature or with an invalid signature are rejected (not ingested).
"""

import json
import logging
import hashlib
from pathlib import Path
from typing import Optional

try:
    from canonical_form import canonical_json as _canonical_form_json
except ImportError:  # pragma: no cover - package import path
    from scripts.canonical_form import canonical_json as _canonical_form_json

logger = logging.getLogger("atested.approval_store")

APPROVAL_STORE_VERSION = "0.1"


def _canonical_json(obj) -> str:
    return _canonical_form_json(obj)


def _normalize_artifact_identity(value: str) -> str:
    return str(value or "").strip().casefold()


def approval_store_hash(store: Optional["ApprovalStore"] = None) -> str:
    """Hash the active approval-store snapshot used for a decision."""
    approvals = [] if store is None else store.all_approvals()
    normalized = {
        "approval_store_version": APPROVAL_STORE_VERSION,
        "active_approvals": sorted(
            approvals,
            key=lambda row: _canonical_json(row),
        ),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def _verify_event_signature(event: dict, public_key) -> bool:
    """Verify Ed25519 signature on an approval/revocation event.

    Returns True if valid, False otherwise.
    """
    sig_b64 = event.get("signature")
    if not sig_b64 or not isinstance(sig_b64, str):
        return False
    try:
        import base64
        from event_model import canonical_json
        from cryptography.exceptions import InvalidSignature

        # Reconstruct signing preimage: record_hash, signature, signing_key_id → None
        copy = dict(event)
        copy["record_hash"] = None
        copy["signature"] = None
        copy["signing_key_id"] = None
        preimage = canonical_json(copy).encode("utf-8")

        # Decode signature (URL-safe base64, no padding)
        padding = "=" * ((4 - len(sig_b64) % 4) % 4)
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + padding)

        public_key.verify(sig_bytes, preimage)
        return True
    except (InvalidSignature, Exception):
        return False


class ApprovalStore:
    """In-memory approval store derived from approval/revocation events.

    Each approval is keyed by the 4-field scope tuple:
    (artifact_identity, governed_family, deployment_context, policy_version).

    The value is the full approval record including approving_operator.

    When require_signatures=True and a public_key is provided, events must
    carry valid Ed25519 signatures to be ingested.
    """

    def __init__(self, *, require_signatures: bool = False, public_key=None):
        self._approvals: dict[tuple, dict] = {}
        self._require_signatures = require_signatures
        self._public_key = public_key
        self._rejected_count = 0

    def ingest_approval(self, event: dict) -> bool:
        """Ingest an opaque_artifact_approval event.

        Returns True if accepted, False if rejected due to signature failure.
        """
        if self._require_signatures and self._public_key is not None:
            if not _verify_event_signature(event, self._public_key):
                self._rejected_count += 1
                logger.warning(
                    "Rejected unsigned/invalid-signature approval: %s",
                    event.get("event_id", "?"),
                )
                return False

        key = self._scope_key(event)
        self._approvals[key] = {
            "artifact_identity": event["artifact_identity"],
            "approving_operator": event["approving_operator"],
            "governed_family": event["governed_family"],
            "deployment_context": event["deployment_context"],
            "policy_version": event["policy_version"],
            "event_id": event.get("event_id"),
            "timestamp_utc": event.get("timestamp_utc"),
        }
        return True

    def ingest_revocation(self, event: dict) -> bool:
        """Ingest an opaque_artifact_revocation event, removing the approval.

        Returns True if accepted, False if rejected due to signature failure.
        """
        if self._require_signatures and self._public_key is not None:
            if not _verify_event_signature(event, self._public_key):
                self._rejected_count += 1
                logger.warning(
                    "Rejected unsigned/invalid-signature revocation: %s",
                    event.get("event_id", "?"),
                )
                return False

        key = self._scope_key(event)
        self._approvals.pop(key, None)
        return True

    @property
    def rejected_count(self) -> int:
        """Number of events rejected due to signature verification failure."""
        return self._rejected_count

    def lookup(
        self,
        artifact_identity: str,
        governed_family: str,
        deployment_context: str,
        policy_version: str,
    ) -> Optional[dict]:
        """Look up whether a valid approval exists for the given scope.

        Returns the approval record if all 5 scope fields match
        (artifact_identity + governed_family + deployment_context +
        policy_version conjunctively, with approving_operator stored
        in the record). Returns None if no matching approval exists.
        """
        key = (
            _normalize_artifact_identity(artifact_identity),
            governed_family,
            deployment_context,
            policy_version,
        )
        return self._approvals.get(key)

    def all_approvals(self) -> list[dict]:
        """Return all current approvals (for testing/inspection)."""
        return list(self._approvals.values())

    def _scope_key(self, event: dict) -> tuple:
        return (
            _normalize_artifact_identity(event["artifact_identity"]),
            event["governed_family"],
            event["deployment_context"],
            event["policy_version"],
        )


def load_approval_store_from_events(
    events: list[dict],
    *,
    require_signatures: bool = False,
    public_key=None,
) -> ApprovalStore:
    """Build an ApprovalStore from a list of approval/revocation events.

    Events are processed in order. Later revocations override earlier
    approvals for the same scope.
    """
    store = ApprovalStore(
        require_signatures=require_signatures, public_key=public_key,
    )
    for event in events:
        event_type = event.get("event_type")
        if event_type == "opaque_artifact_approval":
            store.ingest_approval(event)
        elif event_type == "opaque_artifact_revocation":
            store.ingest_revocation(event)
    return store


def load_approval_store_from_chain(
    chain_path: str,
    *,
    require_signatures: bool = False,
    public_key=None,
) -> ApprovalStore:
    """Build an ApprovalStore from a JSONL decision chain file.

    Scans the chain for approval and revocation events and builds
    the derived index.
    """
    events = []
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event_type") in ("opaque_artifact_approval", "opaque_artifact_revocation"):
                events.append(rec)
    return load_approval_store_from_events(
        events, require_signatures=require_signatures, public_key=public_key,
    )
