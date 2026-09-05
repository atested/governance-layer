"""State-safe operator review primitives used by dashboard validation.

The view model is deliberately derived from governance records: it never
claims execution for a decision that was withheld and it exposes only the
approval lifecycle action that can be taken in the current state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable, Mapping


_VALID_STATES = frozenset({"ALLOW", "DENY", "pending-approval", "approved", "revoked"})
_ACTIONS = {
    "ALLOW": (),
    "DENY": ("approve",),
    "pending-approval": ("approve",),
    "approved": ("revoke",),
    "revoked": ("approve",),
}


def decision_review(record: Mapping) -> dict:
    """Return an operator review that is mutually consistent for every state."""
    state = str(record.get("state") or record.get("policy_decision") or "").strip()
    if state not in _VALID_STATES:
        raise ValueError("unsupported governance decision state")
    operation = record.get("operation_description") or record.get("operation") or record.get("tool_name")
    if not operation:
        raise ValueError("a governance review requires an operation")
    # Approval lifecycle states describe authorization, not an invocation.
    # Only an ALLOW decision may report execution, and only when its source
    # record says it was executed.
    executed = bool(record.get("executed", state == "ALLOW")) if state == "ALLOW" else False
    return {
        "operation": operation,
        "outcome": state,
        "reason_codes": list(record.get("reason_codes") or ([record["reason_code"]] if record.get("reason_code") else [])),
        "evidence": deepcopy(record.get("evidence") or {}),
        "executed": executed,
        "execution_status": "executed" if executed else "not executed",
        "available_actions": list(_ACTIONS[state]),
    }


@dataclass
class WindowNavigator:
    """Bounded child-window stack retaining persistent dashboard signals."""

    operator_identity: str
    license_signal: str
    notifications: tuple[str, ...] = ()

    def __post_init__(self):
        self._stack: list[dict] = []

    def open(self, view: Mapping) -> dict:
        if len(self._stack) >= 2:
            raise ValueError("maximum child-window depth is two")
        self._stack.append(deepcopy(dict(view)))
        return self.current()

    def close(self) -> dict | None:
        if not self._stack:
            return None
        self._stack.pop()
        return self.current() if self._stack else None

    def current(self) -> dict:
        if not self._stack:
            raise ValueError("no child window is open")
        return {
            "depth": len(self._stack),
            "view": deepcopy(self._stack[-1]),
            "operator_identity": self.operator_identity,
            "license_signal": self.license_signal,
            "notifications": list(self.notifications),
        }


def filter_activity(records: Iterable[Mapping], *, start_time=None, end_time=None,
                    tier=None, decision=None, machine_id=None) -> list[dict]:
    """Apply the four investigation filters conjunctively and without mutation."""
    selected = []
    for record in records:
        timestamp = record.get("timestamp_utc", "")
        record_tier = record.get("confidence_tier", record.get("classification", {}).get("confidence_tier"))
        record_decision = record.get("policy_decision", record.get("state"))
        if start_time and timestamp < start_time:
            continue
        if end_time and timestamp > end_time:
            continue
        if tier is not None and str(record_tier) != str(tier):
            continue
        if decision and record_decision != decision:
            continue
        if machine_id and record.get("machine_id") != machine_id:
            continue
        selected.append(deepcopy(dict(record)))
    return selected


def trace_summary(summary: Mapping, records: Iterable[Mapping]) -> list[dict]:
    """Resolve a summary's record IDs and reject contradictory evidence."""
    index = {}
    for record in records:
        for key in ("record_id", "request_id", "event_id", "record_hash"):
            if record.get(key):
                index[str(record[key])] = record
    ids = summary.get("record_ids") or summary.get("evidence_ids") or []
    if not ids:
        raise ValueError("summary has no navigable supporting records")
    resolved = []
    for record_id in ids:
        record = index.get(str(record_id))
        if record is None:
            raise ValueError(f"supporting record not found: {record_id}")
        for summary_key, record_key in (("decision", "policy_decision"), ("operation", "operation_description"),
                                        ("policy_context", "policy_context"), ("integrity_state", "integrity_state")):
            if summary.get(summary_key) is not None and summary[summary_key] != record.get(record_key):
                raise ValueError(f"summary {summary_key} contradicts record {record_id}")
        resolved.append(deepcopy(dict(record)))
    return resolved
