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
"""

import json
from pathlib import Path
from typing import Optional


APPROVAL_STORE_VERSION = "0.1"


class ApprovalStore:
    """In-memory approval store derived from approval/revocation events.

    Each approval is keyed by the 4-field scope tuple:
    (artifact_identity, governed_family, deployment_context, policy_version).

    The value is the full approval record including approving_operator.
    """

    def __init__(self):
        self._approvals: dict[tuple, dict] = {}

    def ingest_approval(self, event: dict) -> None:
        """Ingest an opaque_artifact_approval event."""
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

    def ingest_revocation(self, event: dict) -> None:
        """Ingest an opaque_artifact_revocation event, removing the approval."""
        key = self._scope_key(event)
        self._approvals.pop(key, None)

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
        key = (artifact_identity, governed_family, deployment_context, policy_version)
        return self._approvals.get(key)

    def all_approvals(self) -> list[dict]:
        """Return all current approvals (for testing/inspection)."""
        return list(self._approvals.values())

    def _scope_key(self, event: dict) -> tuple:
        return (
            event["artifact_identity"],
            event["governed_family"],
            event["deployment_context"],
            event["policy_version"],
        )


def load_approval_store_from_events(events: list[dict]) -> ApprovalStore:
    """Build an ApprovalStore from a list of approval/revocation events.

    Events are processed in order. Later revocations override earlier
    approvals for the same scope.
    """
    store = ApprovalStore()
    for event in events:
        event_type = event.get("event_type")
        if event_type == "opaque_artifact_approval":
            store.ingest_approval(event)
        elif event_type == "opaque_artifact_revocation":
            store.ingest_revocation(event)
    return store


def load_approval_store_from_chain(chain_path: str) -> ApprovalStore:
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
    return load_approval_store_from_events(events)
