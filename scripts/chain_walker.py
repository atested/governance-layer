"""Shared Chain Walker readout helpers.

This module is intentionally independent from dashboard/server.py and UI code.
It normalizes chain records into stable row dictionaries, renders deterministic
narrative text from those rows, and classifies records that deserve alert
navigation focus.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


ALERT_SEVERITIES = frozenset({"alert", "critical", "critical_alert", "error", "warning"})
ALERT_EVENT_TYPES = frozenset(
    {
        "chain_file_missing",
        "chain_file_truncated",
        "chain_integrity_violation",
        "chain_record_count_mismatch",
        "chain_tail_hash_mismatch",
        "license_downgraded",
        "license_expiration_warning",
        "license_expired",
        "license_modified",
        "license_revoked",
        "machine_revoked",
        "opaque_artifact_approval",
        "opaque_artifact_revocation",
        "policy_rules_changed",
        "proxy_code_hash_changed",
    }
)
APPROVAL_EVENT_TYPES = frozenset({"opaque_artifact_approval"})
REVOCATION_EVENT_TYPES = frozenset({"opaque_artifact_revocation"})
INTEGRITY_EVENT_TYPES = frozenset(
    {
        "chain_file_missing",
        "chain_file_truncated",
        "chain_integrity_violation",
        "chain_record_count_mismatch",
        "chain_tail_hash_mismatch",
        "policy_rules_changed",
        "policy_rules_loaded",
        "proxy_code_hash_changed",
        "proxy_startup_code_hash",
    }
)
LICENSE_EVENT_PREFIXES = ("license_", "machine_")


def load_walker_rows(chain_path: Path) -> list[dict[str, Any]]:
    """Load a JSONL chain file as normalized walker rows.

    Invalid JSON lines become malformed rows instead of aborting the whole
    readout. This lets the walker center on the bad line in later phases.
    """

    rows: list[dict[str, Any]] = []
    if not chain_path.exists():
        return rows
    with chain_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows.append(normalize_chain_line(line, sequence=index))
    return rows


def normalize_chain_line(line: str, *, sequence: int) -> dict[str, Any]:
    """Parse one JSONL chain line into a normalized walker row."""

    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        return _malformed_row(sequence, f"invalid JSON: {exc.msg}")
    return normalize_record(record, sequence=sequence)


def normalize_records(records: Iterable[Any], *, start_sequence: int = 1) -> list[dict[str, Any]]:
    """Normalize records while preserving their input order."""

    return [
        normalize_record(record, sequence=index)
        for index, record in enumerate(records, start=start_sequence)
    ]


def normalize_record(record: Any, *, sequence: int) -> dict[str, Any]:
    """Normalize one chain record into the Chain Walker row format."""

    if not isinstance(record, Mapping):
        return _malformed_row(sequence, f"expected object, got {type(record).__name__}")

    event_type = _string(record.get("event_type"))
    record_type = _string(record.get("record_type"))
    decision = _decision(record)
    category = _category(record, event_type, record_type, decision)
    action = _action(record)
    action_type = _action_type(record)
    target = _target(record)
    tier = _tier(record)
    user = _user(record)
    row = {
        "sequence": sequence,
        "timestamp_utc": _string(record.get("timestamp_utc")),
        "category": category,
        "decision": decision,
        "action": action,
        "action_type": action_type,
        "target": target,
        "tier": tier,
        "user": user,
        "hash": _short_hash(_string(record.get("record_hash"))),
        "record_hash": _string(record.get("record_hash")),
        "record_id": _record_id(record),
        "event_type": event_type,
        "record_type": record_type,
        "signature_status": _signature_status(record),
        "malformed": False,
        "malformed_reason": "",
    }
    row["alert"] = is_alert_event(row, record)
    row["alert_reason"] = alert_reason(row, record)
    row["narrative"] = narrative_for_row(row)
    return row


def is_alert_event(row_or_record: Mapping[str, Any], record: Optional[Mapping[str, Any]] = None) -> bool:
    """Return True when the row/record should stop playback or alert jumps."""

    source = record or row_or_record
    event_type = _string(source.get("event_type"))
    decision = _decision(source) or _string(row_or_record.get("decision")).upper()
    if _bool(row_or_record.get("malformed")):
        return True
    if decision == "DENY":
        return True
    if event_type in ALERT_EVENT_TYPES:
        return True
    if _string(source.get("severity")).lower() in ALERT_SEVERITIES:
        return True
    if _string(source.get("level")).lower() in ALERT_SEVERITIES:
        return True
    if _string(source.get("status")).lower() in {"blocked", "failed", "revoked", "expired"}:
        return True
    return False


def alert_reason(row_or_record: Mapping[str, Any], record: Optional[Mapping[str, Any]] = None) -> str:
    """Return a deterministic alert reason for UI status text and exports."""

    source = record or row_or_record
    event_type = _string(source.get("event_type"))
    decision = _decision(source) or _string(row_or_record.get("decision")).upper()
    if _bool(row_or_record.get("malformed")):
        return "Malformed chain record"
    if decision == "DENY":
        return "Policy denial"
    if event_type in APPROVAL_EVENT_TYPES:
        return "Approval recorded"
    if event_type in REVOCATION_EVENT_TYPES:
        return "Revocation recorded"
    if event_type in INTEGRITY_EVENT_TYPES:
        return "Integrity event"
    if event_type.startswith(LICENSE_EVENT_PREFIXES) or event_type in ALERT_EVENT_TYPES:
        return "License or machine state event"
    severity = _string(source.get("severity") or source.get("level")).lower()
    if severity in ALERT_SEVERITIES:
        return f"{severity.capitalize()} severity"
    status = _string(source.get("status")).lower()
    if status in {"blocked", "failed", "revoked", "expired"}:
        return f"{status.capitalize()} status"
    return ""


def narrative_for_row(row: Mapping[str, Any]) -> str:
    """Render a deterministic plain-language narrative from normalized row data."""

    if _bool(row.get("malformed")):
        reason = _string(row.get("malformed_reason")) or "could not be normalized"
        return f"MALFORMED: chain record {row.get('sequence')} {reason}."

    event_type = _string(row.get("event_type"))
    decision = _string(row.get("decision")).upper()
    action = _or_unknown(row.get("action"))
    target = _string(row.get("target"))
    user = _or_unknown(row.get("user"), fallback="unknown actor")
    tier = _string(row.get("tier"))
    hash_value = _string(row.get("hash"))

    if decision == "ALLOW":
        text = f"ALLOW: {user} ran {action}"
        if target:
            text += f" on {target}"
        if tier:
            text += f" at tier {tier}"
        return _append_hash(text, hash_value)

    if decision == "DENY":
        text = f"DENY: {user} attempted {action}"
        if target:
            text += f" on {target}"
        text += ". Policy denied before execution"
        if tier:
            text += f" at tier {tier}"
        return _append_hash(text, hash_value)

    if event_type in APPROVAL_EVENT_TYPES:
        operator = _or_unknown(row.get("user"), fallback="unknown operator")
        artifact = target or _or_unknown(row.get("record_id"), fallback="unknown artifact")
        return _append_hash(
            f"APPROVAL: operator {operator} approved artifact {artifact} for future matching operations",
            hash_value,
        )

    if event_type in REVOCATION_EVENT_TYPES:
        operator = _or_unknown(row.get("user"), fallback="unknown operator")
        artifact = target or _or_unknown(row.get("record_id"), fallback="unknown artifact")
        return _append_hash(
            f"REVOCATION: operator {operator} revoked approval {artifact}; matching operations return to policy evaluation",
            hash_value,
        )

    if event_type == "proxy_startup_code_hash":
        current = target or _or_unknown(row.get("record_id"), fallback="unknown hash")
        return _append_hash(f"INTEGRITY: proxy started with code hash {current}", hash_value)

    if event_type == "proxy_code_hash_changed":
        return _append_hash(f"INTEGRITY: proxy code hash changed ({target or 'hash change recorded'})", hash_value)

    if event_type == "policy_rules_loaded":
        current = target or _or_unknown(row.get("record_id"), fallback="unknown hash")
        return _append_hash(f"INTEGRITY: policy rules hash {current} loaded", hash_value)

    if event_type == "policy_rules_changed":
        return _append_hash(f"INTEGRITY: policy rules changed ({target or 'hash change recorded'})", hash_value)

    if event_type in INTEGRITY_EVENT_TYPES:
        label = _event_label(event_type)
        return _append_hash(f"INTEGRITY: {label} recorded ({target or 'no target'})", hash_value)

    if event_type.startswith(LICENSE_EVENT_PREFIXES):
        label = _event_label(event_type)
        subject = target or _or_unknown(row.get("record_id"), fallback="license state")
        return _append_hash(f"LICENSE: {label} recorded for {subject}", hash_value)

    if event_type:
        label = _event_label(event_type)
        subject = target or _or_unknown(row.get("record_id"), fallback="chain record")
        return _append_hash(f"EVENT: {label} recorded for {subject}", hash_value)

    text = f"RECORD: {row.get('category') or 'unknown'}"
    if action != "unknown":
        text += f" {action}"
    if target:
        text += f" on {target}"
    return _append_hash(text, hash_value)


def apply_walker_filters(
    rows: Iterable[Mapping[str, Any]],
    *,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    decision: Optional[str] = None,
    action_type: Optional[str] = None,
    tier: Optional[str] = None,
    user: Optional[str] = None,
    target: Optional[str] = None,
    category: Optional[str] = None,
    action: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Apply Audit-style filters to normalized walker rows."""

    result: list[dict[str, Any]] = []
    wanted_decision = _string(decision).upper()
    for row in rows:
        ts = _string(row.get("timestamp_utc"))
        if start_time and ts and ts < start_time:
            continue
        if end_time and ts and ts > end_time:
            continue
        if wanted_decision and _string(row.get("decision")).upper() != wanted_decision:
            continue
        if action_type and _string(row.get("action_type")) != str(action_type):
            continue
        if tier and _string(row.get("tier")) != str(tier):
            continue
        if user and user not in _string(row.get("user")):
            continue
        if target and target not in _string(row.get("target")):
            continue
        if category and _string(row.get("category")) != str(category):
            continue
        if action and action not in _string(row.get("action")):
            continue
        result.append(dict(row))
    return result


def _malformed_row(sequence: int, reason: str) -> dict[str, Any]:
    row = {
        "sequence": sequence,
        "timestamp_utc": "",
        "category": "malformed",
        "decision": "",
        "action": "",
        "action_type": "",
        "target": "",
        "tier": "",
        "user": "",
        "hash": "",
        "record_hash": "",
        "record_id": f"malformed-{sequence}",
        "event_type": "",
        "record_type": "",
        "signature_status": "unknown",
        "malformed": True,
        "malformed_reason": reason,
        "alert": True,
        "alert_reason": "Malformed chain record",
    }
    row["narrative"] = narrative_for_row(row)
    return row


def _category(record: Mapping[str, Any], event_type: str, record_type: str, decision: str) -> str:
    if event_type in APPROVAL_EVENT_TYPES:
        return "approval"
    if event_type in REVOCATION_EVENT_TYPES:
        return "revocation"
    if event_type in INTEGRITY_EVENT_TYPES:
        return "integrity"
    if event_type.startswith(LICENSE_EVENT_PREFIXES):
        return "license"
    if event_type == "verification_state_transition":
        return "verification"
    if decision:
        return "action_decision"
    if event_type:
        return "system_event"
    if record_type:
        return record_type
    if "record_hash" in record:
        return "chain_record"
    return "unknown"


def _decision(record: Mapping[str, Any]) -> str:
    value = record.get("policy_decision", record.get("decision", ""))
    if isinstance(value, Mapping):
        return ""
    return _string(value).upper()


def _action(record: Mapping[str, Any]) -> str:
    for key in ("original_tool", "tool", "action", "action_type", "capability_class", "governed_family"):
        value = _string(record.get(key))
        if value:
            return value
    classification = record.get("classification")
    if isinstance(classification, Mapping):
        for key in ("action_type", "tool", "capability_class"):
            value = _string(classification.get(key))
            if value:
                return value
    intent = record.get("intent")
    if isinstance(intent, Mapping):
        return _string(intent.get("requested_action"))
    return ""


def _action_type(record: Mapping[str, Any]) -> str:
    value = _string(record.get("action_type"))
    if value:
        return value
    classification = record.get("classification")
    if isinstance(classification, Mapping):
        return _string(classification.get("action_type"))
    return ""


def _target(record: Mapping[str, Any]) -> str:
    for key in (
        "target",
        "artifact_identity",
        "current_policy_rules_hash",
        "current_proxy_code_hash",
        "license_id",
        "machine_id",
        "governed_family",
    ):
        value = _string(record.get(key))
        if value:
            return value

    for key in ("tool_args_redacted", "normalized_args", "classification"):
        data = record.get(key)
        if not isinstance(data, Mapping):
            continue
        for nested_key in (
            "canonical_path",
            "path",
            "canonical_dst_path",
            "canonical_src_path",
            "command",
            "url",
        ):
            value = _string(data.get(nested_key))
            if value:
                return value
        targets = data.get("targets")
        if isinstance(targets, list) and targets:
            return _string(targets[0])

    intent = record.get("intent")
    if isinstance(intent, Mapping):
        outputs = intent.get("expected_outputs")
        if isinstance(outputs, list) and outputs:
            first = outputs[0]
            if isinstance(first, Mapping):
                value = _string(first.get("value") or first.get("ref"))
                if value:
                    return value
    return ""


def _tier(record: Mapping[str, Any]) -> str:
    for key in ("confidence_tier", "tier"):
        value = _string(record.get(key))
        if value:
            return value
    classification = record.get("classification")
    if isinstance(classification, Mapping):
        return _string(classification.get("confidence_tier"))
    return ""


def _user(record: Mapping[str, Any]) -> str:
    for key in (
        "user_identity",
        "operator",
        "approving_operator",
        "revoking_operator",
        "actor",
        "submitted_by",
    ):
        value = _string(record.get(key))
        if value:
            return value
    return ""


def _record_id(record: Mapping[str, Any]) -> str:
    for key in (
        "request_id",
        "event_id",
        "record_hash",
        "artifact_identity",
        "current_policy_rules_hash",
        "current_proxy_code_hash",
        "license_id",
    ):
        value = _string(record.get(key))
        if value:
            return value
    return ""


def _signature_status(record: Mapping[str, Any]) -> str:
    signature = record.get("signature")
    key_id = record.get("signing_key_id")
    if signature and key_id:
        return "signed"
    if signature or key_id:
        return "partial_signature"
    if "signature" in record or "signing_key_id" in record:
        return "unsigned_legacy"
    return "not_recorded"


def _short_hash(value: str) -> str:
    if not value:
        return ""
    if value.startswith("sha256:"):
        return value[:19]
    return value[:16]


def _append_hash(text: str, hash_value: str) -> str:
    if hash_value:
        return f"{text}. Hash {hash_value}."
    return f"{text}."


def _event_label(event_type: str) -> str:
    return event_type.replace("_", " ")


def _or_unknown(value: Any, *, fallback: str = "unknown") -> str:
    text = _string(value)
    return text if text else fallback


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _bool(value: Any) -> bool:
    return bool(value)
