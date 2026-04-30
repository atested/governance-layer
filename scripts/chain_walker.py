"""Shared Chain Walker readout helpers.

This module is intentionally independent from dashboard/server.py and UI code.
It normalizes chain records into stable row dictionaries, renders deterministic
narrative text from those rows, and classifies records that deserve alert
navigation focus.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


ALERT_SEVERITIES = frozenset({"alert", "critical", "critical_alert", "error", "warning"})
ALERT_EVENT_TYPES = frozenset(
    {
        "chain_file_missing",
        "chain_file_truncated",
        "chain_integrity_violation",
        "chain_record_count_mismatch",
        "chain_started_after_archive",
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
        "chain_started_after_archive",
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


def load_raw_records_range(
    chain_path: Path,
    *,
    start_sequence: int,
    end_sequence: int,
    chain_source: str = "live",
    archive_id: Optional[str] = None,
) -> dict[str, Any]:
    """Extract raw chain records for a sequence range.

    Returns a dict with:
      - records: list of raw parsed JSON records in the range
      - predecessor_hash: record_hash of the record just before start_sequence
        (for verifying linkage at the boundary)
      - start_sequence, end_sequence: actual range covered
      - record_count: number of records returned
      - chain_source, archive_id: echo back
    """
    source_path = chain_path
    if chain_source == "archive":
        if not archive_id:
            return {
                "error": "archive_id is required when chain_source is 'archive'",
                "records": [],
                "predecessor_hash": None,
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
                "record_count": 0,
                "chain_source": chain_source,
                "archive_id": "",
            }
        from chain_archive import get_archive_manifest
        manifest = get_archive_manifest(chain_path, archive_id)
        if not manifest or not manifest.get("archive_chain_path"):
            return {
                "error": f"archive not found: {archive_id}",
                "records": [],
                "predecessor_hash": None,
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
                "record_count": 0,
                "chain_source": chain_source,
                "archive_id": archive_id,
            }
        archive_path = Path(manifest["archive_chain_path"])
        # SEC-2026-005: validate archive_chain_path stays inside archive dir
        from chain_archive import archive_root_for
        expected_root = archive_root_for(chain_path).resolve()
        try:
            resolved = archive_path.resolve(strict=False)
        except (OSError, ValueError):
            return {
                "error": f"archive path invalid: {archive_path}",
                "records": [],
                "predecessor_hash": None,
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
                "record_count": 0,
                "chain_source": chain_source,
                "archive_id": archive_id,
            }
        if not str(resolved).startswith(str(expected_root) + os.sep) and resolved != expected_root:
            return {
                "error": f"archive path escapes archive directory: {archive_path}",
                "records": [],
                "predecessor_hash": None,
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
                "record_count": 0,
                "chain_source": chain_source,
                "archive_id": archive_id,
            }
        if not archive_path.exists():
            return {
                "error": f"archive file missing: {archive_path}",
                "records": [],
                "predecessor_hash": None,
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
                "record_count": 0,
                "chain_source": chain_source,
                "archive_id": archive_id,
            }
        source_path = archive_path

    records: list[dict[str, Any]] = []
    predecessor_hash: Optional[str] = None
    if not source_path.exists():
        return {
            "records": [],
            "predecessor_hash": None,
            "start_sequence": start_sequence,
            "end_sequence": end_sequence,
            "record_count": 0,
            "chain_source": chain_source,
            "archive_id": archive_id or "",
        }

    with source_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if index == start_sequence - 1:
                try:
                    prev = json.loads(stripped)
                    predecessor_hash = prev.get("record_hash")
                except json.JSONDecodeError:
                    predecessor_hash = None
            if start_sequence <= index <= end_sequence:
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    records.append({"_malformed": True, "sequence": index, "raw": stripped[:500]})
            if index > end_sequence:
                break

    return {
        "records": records,
        "predecessor_hash": predecessor_hash,
        "start_sequence": start_sequence,
        "end_sequence": end_sequence,
        "record_count": len(records),
        "chain_source": chain_source,
        "archive_id": archive_id or "",
    }


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
    matched_rule = _string(record.get("matched_rule"))
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
        "matched_rule": matched_rule,
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
        rule = _string(row.get("matched_rule"))
        if rule:
            text += f" under rule {rule}"
        elif tier:
            text += f" at tier {tier}"
        return _append_hash(text, hash_value)

    if decision == "DENY":
        text = f"DENY: {user} attempted {action}"
        if target:
            text += f" on {target}"
        text += ". Policy denied before execution"
        rule = _string(row.get("matched_rule"))
        if rule:
            text += f" by rule {rule}"
        elif tier:
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


def walker_query(
    chain_path: Path,
    *,
    chain_source: str = "live",
    archive_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user_identity: Optional[str] = None,
    tool_name: Optional[str] = None,
    action_type: Optional[str] = None,
    confidence_tier: Optional[str] = None,
    policy_decision: Optional[str] = None,
    event_category: Optional[str] = None,
    center_record_id: Optional[str] = None,
    center_sequence: Optional[int] = None,
    center_index: Optional[int] = None,
    alert_direction: Optional[str] = None,
    radius: int = 5,
) -> dict[str, Any]:
    """Return a centered chain window for the Audit Chain Walker."""

    source_path = chain_path
    source_label = "live"
    archive_manifest = None
    if chain_source == "archive":
        if not archive_id:
            return {"error": "archive_id is required when chain_source is 'archive'",
                    "rows": [], "total_matching": 0}
        from chain_archive import get_archive_manifest
        archive_manifest = get_archive_manifest(chain_path, archive_id)
        if not archive_manifest or not archive_manifest.get("archive_chain_path"):
            return {"error": f"archive not found: {archive_id}",
                    "rows": [], "total_matching": 0}
        archive_path = Path(archive_manifest["archive_chain_path"])
        if not archive_path.exists():
            return {"error": f"archive file missing: {archive_path}",
                    "rows": [], "total_matching": 0}
        source_path = archive_path
        source_label = "archive"

    all_rows = load_walker_rows(source_path)
    filtered = apply_walker_filters(
        all_rows,
        start_time=start_time,
        end_time=end_time,
        decision=policy_decision,
        action_type=action_type,
        tier=confidence_tier,
        user=user_identity,
        target=None,
        category=_category_filter_alias(event_category),
        action=tool_name,
    )
    total = len(filtered)
    if not total:
        return {
            "timestamp_utc": "",
            "chain_source": source_label,
            "archive": archive_manifest,
            "rows": [],
            "total_matching": 0,
            "center_index": 0,
            "center_sequence": None,
            "window_start_index": 0,
            "window_end_index": -1,
            "radius": radius,
            "has_previous": False,
            "has_next": False,
            "has_previous_alert": False,
            "has_next_alert": False,
            "filters": _walker_filter_echo(
                start_time, end_time, user_identity, tool_name, action_type,
                confidence_tier, policy_decision, event_category,
            ),
        }

    idx = _resolve_center_index(
        filtered,
        center_record_id=center_record_id,
        center_sequence=center_sequence,
        center_index=center_index,
    )
    alert_jump_found = False
    if alert_direction in {"next", "previous"}:
        jumped = _resolve_alert_index(filtered, idx, alert_direction)
        alert_jump_found = jumped is not None
        if jumped is not None:
            idx = jumped
    start = max(0, idx - radius)
    end = min(total, idx + radius + 1)
    center = filtered[idx]
    previous_alert = _resolve_alert_index(filtered, idx, "previous")
    next_alert = _resolve_alert_index(filtered, idx, "next")
    return {
        "timestamp_utc": center.get("timestamp_utc", ""),
        "chain_source": source_label,
        "archive": archive_manifest,
        "rows": filtered[start:end],
        "total_matching": total,
        "center_index": idx,
        "center_sequence": center.get("sequence"),
        "window_start_index": start,
        "window_end_index": end - 1,
        "radius": radius,
        "has_previous": idx > 0,
        "has_next": idx < total - 1,
        "has_previous_alert": previous_alert is not None,
        "has_next_alert": next_alert is not None,
        "alert_jump_found": alert_jump_found,
        "filters": _walker_filter_echo(
            start_time, end_time, user_identity, tool_name, action_type,
            confidence_tier, policy_decision, event_category,
        ),
    }


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
        "matched_rule": "",
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


def _resolve_center_index(
    rows: list[dict[str, Any]],
    *,
    center_record_id: Optional[str],
    center_sequence: Optional[int],
    center_index: Optional[int],
) -> int:
    if center_record_id:
        wanted = str(center_record_id)
        for idx, row in enumerate(rows):
            if wanted in {
                _string(row.get("record_id")),
                _string(row.get("record_hash")),
                _string(row.get("hash")),
                _string(row.get("sequence")),
            }:
                return idx
    if center_sequence is not None:
        for idx, row in enumerate(rows):
            if row.get("sequence") == center_sequence:
                return idx
    if center_index is not None:
        return max(0, min(len(rows) - 1, int(center_index)))
    return 0


def _resolve_alert_index(
    rows: list[dict[str, Any]],
    current_index: int,
    direction: str,
) -> Optional[int]:
    if direction == "next":
        search = range(current_index + 1, len(rows))
    else:
        search = range(current_index - 1, -1, -1)
    for idx in search:
        if rows[idx].get("alert"):
            return idx
    return None


def _category_filter_alias(category: Optional[str]) -> Optional[str]:
    aliases = {
        "opaque_approval": "approval",
        "opaque_revocation": "revocation",
        "verification_transition": "verification",
    }
    if category:
        return aliases.get(category, category)
    return None


def _walker_filter_echo(
    start_time: Optional[str],
    end_time: Optional[str],
    user_identity: Optional[str],
    tool_name: Optional[str],
    action_type: Optional[str],
    confidence_tier: Optional[str],
    policy_decision: Optional[str],
    event_category: Optional[str],
) -> dict[str, Optional[str]]:
    return {
        "start_time": start_time,
        "end_time": end_time,
        "user_identity": user_identity,
        "tool_name": tool_name,
        "action_type": action_type,
        "confidence_tier": confidence_tier,
        "policy_decision": policy_decision,
        "event_category": event_category,
    }


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
