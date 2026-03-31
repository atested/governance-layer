#!/usr/bin/env python3
"""
verification.py — Verification state model and probe contract.

Implements the governed-action baseline spec v1.1 §7 verification model
and §10 evidence-bearing probe contract.

Verification state (§7.3):
  - Each governed surface has a verification state: unverified, verified,
    or drift_detected.
  - State transitions are governance-significant events recorded in the
    decision chain as verification_state_transition events.
  - Unknown/unseen surfaces default to unverified.

Valid transition graph:
  unverified     → verified
  verified       → drift_detected
  drift_detected → verified
  drift_detected → unverified

Probe contract (§10):
  - Probes are precise, bounded, evidence-bearing, and optionally nonce-based.
  - ProbeResult carries structured evidence (not bare pass/fail).
  - evaluate_probe_result() determines whether a probe result implies a
    state transition.

Design constraints:
  - Verification state is informational at baseline — no action blocking.
  - governed_family is an opaque string identifier (no normalization).
  - Nonce field exists in ProbeResult but is not validated at baseline.
  - The state tracker is in-memory, rebuilt from chain events on startup
    (same derivation pattern as ApprovalStore).
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from event_model import (
    VERIFICATION_STATES,
    build_non_action_event,
)


# ---------------------------------------------------------------------------
# Valid transition graph (§7.3)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset([
    ("unverified", "verified"),
    ("verified", "drift_detected"),
    ("drift_detected", "verified"),
    ("drift_detected", "unverified"),
])


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Return True if from_state → to_state is a valid verification transition."""
    return (from_state, to_state) in VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# Verification state tracker (§7.3)
# ---------------------------------------------------------------------------

class VerificationStateTracker:
    """Per-surface verification state tracker.

    Tracks the current verification state for each governed surface.
    Surfaces not explicitly tracked default to 'unverified'.
    """

    def __init__(self):
        self._states: dict[str, str] = {}

    def get_state(self, governed_family: str) -> str:
        """Return the current verification state for a governed surface.

        Returns 'unverified' for surfaces that have never been seen.
        """
        return self._states.get(governed_family, "unverified")

    def transition(
        self,
        governed_family: str,
        to_state: str,
        prev_record_hash: Optional[str] = None,
        compound_metadata: Optional[dict] = None,
    ) -> dict:
        """Transition a surface to a new verification state.

        Validates the transition against the allowed graph. On success,
        updates internal state and returns the verification_state_transition
        event dict (ready for chain append).

        Raises ValueError if the transition is invalid.
        """
        from_state = self.get_state(governed_family)

        if from_state == to_state:
            raise ValueError(
                f"no-op transition: {governed_family} is already in state {to_state!r}"
            )

        if not is_valid_transition(from_state, to_state):
            raise ValueError(
                f"invalid transition for {governed_family}: "
                f"{from_state!r} → {to_state!r} "
                f"(valid transitions: {sorted(VALID_TRANSITIONS)})"
            )

        event = build_non_action_event(
            "verification_state_transition",
            {
                "governed_family": governed_family,
                "from_state": from_state,
                "to_state": to_state,
            },
            prev_record_hash=prev_record_hash,
            compound_metadata=compound_metadata,
        )

        self._states[governed_family] = to_state
        return event

    def ingest_transition_event(self, event: dict) -> None:
        """Replay a verification_state_transition event into the tracker.

        Used during chain reconstruction. Does not validate the transition
        graph — the chain is assumed to contain only valid transitions
        (they were validated at recording time).
        """
        governed_family = event["governed_family"]
        to_state = event["to_state"]
        self._states[governed_family] = to_state

    def all_states(self) -> dict[str, str]:
        """Return a copy of all tracked surface states (for testing/inspection)."""
        return dict(self._states)


# ---------------------------------------------------------------------------
# Chain-derived state reconstruction
# ---------------------------------------------------------------------------

def load_verification_state_from_events(
    events: list[dict],
) -> VerificationStateTracker:
    """Build a VerificationStateTracker from a list of transition events.

    Events are processed in order. Each event updates the surface state.
    """
    tracker = VerificationStateTracker()
    for event in events:
        if event.get("event_type") == "verification_state_transition":
            tracker.ingest_transition_event(event)
    return tracker


def load_verification_state_from_chain(
    chain_path: str,
) -> VerificationStateTracker:
    """Build a VerificationStateTracker from a JSONL decision chain file.

    Scans the chain for verification_state_transition events and replays
    them to reconstruct the current per-surface verification state.
    """
    events = []
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event_type") == "verification_state_transition":
                events.append(rec)
    return load_verification_state_from_events(events)


# ---------------------------------------------------------------------------
# Routing hook contract (§7.3)
# ---------------------------------------------------------------------------

def check_verification_state(
    governed_family: str,
    tracker: VerificationStateTracker,
) -> str:
    """Return the current verification state for a governed surface.

    This is the routing hook contract for the governance flow. The caller
    (governed_tool or equivalent) uses this to annotate the action record
    with the surface's verification state at decision time.

    At baseline, verification state is informational — it does not gate
    or block actions. The returned state is one of:
      'unverified', 'verified', 'drift_detected'
    """
    return tracker.get_state(governed_family)


# ---------------------------------------------------------------------------
# Probe result contract (§10)
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Result of an evidence-bearing probe (§10.1).

    Attributes:
        probe_id: Unique identifier for this probe execution.
        governed_family: The governed surface that was probed.
        property_tested: A short description of the behavioral property tested.
        evidence: Structured evidence dict. Must contain concrete observations,
                  not bare pass/fail. Probe-type-specific content.
        passed: Whether the probe considers the tested property to be correct.
        nonce: Optional nonce used to ensure response freshness (§10.1).
               Present but not validated at baseline.
        timestamp_utc: ISO 8601 timestamp of probe execution.
    """
    probe_id: str
    governed_family: str
    property_tested: str
    evidence: dict
    passed: bool
    nonce: Optional[str] = None
    timestamp_utc: Optional[str] = None


def evaluate_probe_result(
    result: ProbeResult,
    tracker: VerificationStateTracker,
) -> Optional[str]:
    """Determine whether a probe result implies a state transition.

    Returns the target state if a transition should occur, or None if
    the current state is already consistent with the probe outcome.

    Transition logic:
      - Probe passed + surface is unverified → 'verified'
        (initial certification)
      - Probe passed + surface is drift_detected → 'verified'
        (recertification after drift)
      - Probe passed + surface is verified → None
        (no change needed)
      - Probe failed + surface is verified → 'drift_detected'
        (drift detection)
      - Probe failed + surface is unverified → None
        (already unverified, no change)
      - Probe failed + surface is drift_detected → None
        (already in drift state)
    """
    current = tracker.get_state(result.governed_family)

    if result.passed:
        if current in ("unverified", "drift_detected"):
            return "verified"
        return None
    else:
        if current == "verified":
            return "drift_detected"
        return None
