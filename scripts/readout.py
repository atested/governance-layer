#!/usr/bin/env python3
"""
readout.py — Governed Action Status Record assembly, Governance Activity
Projection, and Audit Query/Report functions for operator readout.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from approval_store import ApprovalStore, load_approval_store_from_chain, load_approval_store_from_events
from verification import VerificationStateTracker, load_verification_state_from_chain, load_verification_state_from_events


REPO = Path(__file__).resolve().parents[1]
OPACITY_METRICS_PATH = REPO / "scripts" / "opacity-metrics.py"
VERIFY_RECORD_PATH = REPO / "scripts" / "verify-record.py"


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_opacity_metrics_module():
    spec = importlib.util.spec_from_file_location("opacity_metrics_impl", OPACITY_METRICS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load opacity metrics from {OPACITY_METRICS_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_verify_record_module():
    spec = importlib.util.spec_from_file_location("verify_record_impl", VERIFY_RECORD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load record verifier from {VERIFY_RECORD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_chain_rows(chain_path: Path) -> list[dict]:
    if not chain_path.exists():
        return []
    rows: list[dict] = []
    with open(chain_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


_integrity_cache: dict[str, Any] = {"mtime": 0.0, "size": 0, "result": None}


def check_chain_integrity(chain_path: Path) -> dict:
    """Verify structural integrity of the chain (hash linkage and record validity).

    This checks cryptographic hash consistency, NOT signing policy enforcement.
    Unsigned records are accepted — the integrity check verifies that hashes
    are correct and linked, not that a signing key was used.

    Results are cached by file mtime + size to avoid re-verifying the entire
    chain on every dashboard request.
    """
    if not chain_path.exists():
        return {"status": "ok", "checked": False, "chain_event_count": 0}

    import os as _os

    try:
        st = chain_path.stat()
        mtime, size = st.st_mtime, st.st_size
    except OSError:
        mtime, size = 0.0, 0

    if (
        _integrity_cache["result"] is not None
        and _integrity_cache["mtime"] == mtime
        and _integrity_cache["size"] == size
    ):
        return _integrity_cache["result"]

    verify_record_mod = _load_verify_record_module()
    prev_hash: Optional[str] = None
    line_no = 0
    breaks: list[dict] = []

    def _record_break(rec: Optional[dict], reason: str) -> None:
        breaks.append({
            "line": line_no,
            "broken_at": (rec.get("event_id") or rec.get("request_id") if rec else None) or f"line:{line_no}",
            "reason": reason,
        })

    # Temporarily allow unsigned records during integrity verification.
    # This function checks hash linkage, not signing compliance.
    old_dev = _os.environ.get("GOV_SIGNING_DEV_MODE")
    _os.environ["GOV_SIGNING_DEV_MODE"] = "1"
    try:
        with open(chain_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                line_no += 1
                try:
                    rec = json.loads(stripped)
                except json.JSONDecodeError:
                    _record_break(None, "invalid_json")
                    # Reset linkage; can't continue from an unparseable record.
                    prev_hash = None
                    continue

                rc, lines = verify_record_mod.verify_record_dict(rec)
                if rc != 0:
                    _record_break(rec, lines[0].replace("FAIL: ", "") if lines else "record_verification_failed")
                    prev_hash = rec.get("record_hash")
                    continue

                link = rec.get("prev_record_hash")
                if line_no > 1 and "prev_record_hash" in rec and link != prev_hash:
                    _record_break(rec, "prev_record_hash_mismatch")
                    prev_hash = rec.get("record_hash")
                    continue

                prev_hash = rec.get("record_hash")
    finally:
        if old_dev is None:
            _os.environ.pop("GOV_SIGNING_DEV_MODE", None)
        else:
            _os.environ["GOV_SIGNING_DEV_MODE"] = old_dev

    if breaks:
        first = breaks[0]
        result = {
            "status": "broken",
            "checked": True,
            "chain_event_count": line_no,
            "broken_at": first["broken_at"],
            "reason": first["reason"],
            "break_count": len(breaks),
            "breaks": breaks,
        }
        _integrity_cache["mtime"] = mtime
        _integrity_cache["size"] = size
        _integrity_cache["result"] = result
        return result

    result = {"status": "ok", "checked": True, "chain_event_count": line_no, "break_count": 0, "breaks": []}
    _integrity_cache["mtime"] = mtime
    _integrity_cache["size"] = size
    _integrity_cache["result"] = result
    return result


def _verification_evidence(rows: list[dict]) -> dict[str, Optional[str]]:
    evidence: dict[str, Optional[str]] = {}
    for row in rows:
        if row.get("event_type") == "verification_state_transition":
            evidence[str(row.get("governed_family"))] = row.get("event_id")
    return evidence


def _approval_projection(
    approval_store: ApprovalStore,
    governed_family: Optional[str] = None,
) -> list[dict]:
    approvals = []
    for approval in approval_store.all_approvals():
        if governed_family is not None and approval.get("governed_family") != governed_family:
            continue
        approvals.append(
            {
                "artifact_identity": approval.get("artifact_identity", ""),
                "approving_operator": approval.get("approving_operator", ""),
                "governed_family": approval.get("governed_family", ""),
                "deployment_context": approval.get("deployment_context", ""),
                "policy_version": approval.get("policy_version", ""),
                "event_id": approval.get("event_id"),
                "timestamp_utc": approval.get("timestamp_utc"),
            }
        )
    approvals.sort(
        key=lambda row: (
            str(row.get("artifact_identity", "")),
            str(row.get("approving_operator", "")),
            str(row.get("timestamp_utc", "")),
        )
    )
    return approvals


def assemble_governance_status_record(
    chain_path: Path,
    verification_tracker: VerificationStateTracker,
    approval_store: ApprovalStore,
    *,
    window: Optional[int] = None,
) -> dict:
    rows = load_chain_rows(chain_path)
    integrity = check_chain_integrity(chain_path)
    metrics_rows = rows[-int(window):] if window else rows
    opacity_metrics = _load_opacity_metrics_module().derive_metrics(metrics_rows)
    verification_states = verification_tracker.all_states()
    drift = sorted([family for family, state in verification_states.items() if state == "drift_detected"])
    reconstructed_verification = (
        load_verification_state_from_events(rows).all_states() if rows else {}
    )
    reconstructed_approval_store = (
        load_approval_store_from_events(rows) if rows else ApprovalStore()
    )
    approvals = _approval_projection(approval_store)
    reconstructed_approvals = _approval_projection(reconstructed_approval_store)

    return {
        "timestamp_utc": _now_utc_z(),
        "chain_event_count": len(rows),
        "chain_integrity": "ok" if integrity["status"] == "ok" else {"broken_at": integrity["broken_at"]},
        "reconstruction_status": {
            "verification_state": "ok" if verification_states == reconstructed_verification else "mismatch",
            "approval_state": "ok" if approvals == reconstructed_approvals else "mismatch",
        },
        "verification_state": verification_states,
        "surfaces_in_drift": drift,
        "active_approvals_count": len(approvals),
        "approval_state": {
            "active_approvals": approvals,
            "evidence_event_ids": [row.get("event_id") for row in approvals if row.get("event_id")],
        },
        "opacity_posture": {
            "transparent_count": opacity_metrics["transparent_vs_opaque_proportion"]["transparent_actions"],
            "opaque_count": opacity_metrics["transparent_vs_opaque_proportion"]["opaque_encounters"],
            "transparent_pct": opacity_metrics["transparent_vs_opaque_proportion"]["transparent_proportion"],
            "evidence_window_count": len(metrics_rows),
        },
        "runtime_outcome_summary": {
            "opaque_path_encounter_frequency": opacity_metrics["opaque_path_encounter_frequency"],
            "opaque_resolution_distribution": opacity_metrics["resolution_distribution"],
        },
        "transparency_metric": compute_transparency_metric(metrics_rows),
    }


def governance_approvals_view(
    chain_path: Path,
    approval_store: ApprovalStore,
    *,
    governed_family: Optional[str] = None,
) -> dict:
    approvals = _approval_projection(approval_store, governed_family=governed_family)
    return {
        "timestamp_utc": _now_utc_z(),
        "active_approvals": approvals,
        "total_count": len(approvals),
        "chain_event_count": len(load_chain_rows(chain_path)),
    }


def governance_verification_view(
    chain_path: Path,
    verification_tracker: VerificationStateTracker,
    *,
    governed_family: Optional[str] = None,
) -> dict:
    rows = load_chain_rows(chain_path)
    evidence = _verification_evidence(rows)
    states = verification_tracker.all_states()
    surfaces = {}
    for family, state in sorted(states.items()):
        if governed_family is not None and family != governed_family:
            continue
        surfaces[family] = {
            "current_state": state,
            "last_transition_event_id": evidence.get(family),
        }
    return {
        "timestamp_utc": _now_utc_z(),
        "surfaces": surfaces,
        "surfaces_in_drift": sorted([family for family, data in surfaces.items() if data["current_state"] == "drift_detected"]),
        "total_tracked": len(surfaces),
    }


# ---------------------------------------------------------------------------
# Governance Activity Projection (GAP)
# ---------------------------------------------------------------------------

EVENT_CATEGORIES = frozenset([
    "action_decision",
    "verification_transition",
    "opaque_approval",
    "opaque_revocation",
    "opaque_invocation_decision",
    "ungoverned_observation",
])

_EVENT_TYPE_TO_CATEGORY = {
    "verification_state_transition": "verification_transition",
    "opaque_artifact_approval": "opaque_approval",
    "opaque_artifact_revocation": "opaque_revocation",
    "opaque_invocation_decision": "opaque_invocation_decision",
    "ungoverned_operation_observed": "ungoverned_observation",
}


def _artifact_identity_prefix(identity: str) -> str:
    """Return first 16 hex chars after 'sha256:' prefix."""
    if identity.startswith("sha256:"):
        return identity[7:23]
    return identity[:16]


def _normalize_activity_entry(rec: dict, sequence_position: int) -> Optional[dict]:
    """Normalize a chain record into a GAP activity entry.

    Returns None if the record does not map to a recognized event category.
    """
    event_type = rec.get("event_type")
    category = _EVENT_TYPE_TO_CATEGORY.get(str(event_type)) if event_type else None

    if category is None:
        # Action record (no event_type field means it's a governed-action decision)
        if "record_type" not in rec and "policy_decision" not in rec:
            return None
        category = "action_decision"

    governed_family = ""
    summary = ""
    detail: dict = {}
    evidence: dict = {}

    if category == "action_decision":
        is_v2 = rec.get("record_version") == "2.0"
        tool_name = rec.get("original_tool") if is_v2 else None
        if not tool_name:
            tool_name = rec.get("tool", rec.get("capability_class", "unknown"))
        policy_decision = rec.get("policy_decision", "unknown")
        record_type = rec.get("record_type", "")
        governed_family = rec.get("governed_family", "")

        classification = rec.get("classification", {})
        confidence_tier = classification.get("confidence_tier") if is_v2 else None
        action_type = classification.get("action_type", "") if is_v2 else ""
        matched_rule = rec.get("matched_rule", "") if is_v2 else ""

        if confidence_tier is not None:
            summary = f"{tool_name} \u2192 {policy_decision} (Tier {confidence_tier})"
        else:
            summary = f"{tool_name} \u2192 {policy_decision}"

        # Extract primary target from classification targets list
        targets = classification.get("targets", []) if is_v2 else []
        target = targets[0] if targets else ""

        detail = {
            "tool_name": tool_name,
            "policy_decision": policy_decision,
            "record_type": record_type,
            "verification_state": rec.get("verification_state", ""),
            "target": target,
        }
        if is_v2:
            detail["confidence_tier"] = confidence_tier
            detail["action_type"] = action_type
            detail["matched_rule"] = matched_rule
            detail["scope"] = classification.get("scope", "")

        evidence = {
            "request_id": rec.get("request_id", ""),
            "record_hash": rec.get("record_hash", ""),
            "policy_decision": policy_decision,
        }

    elif category == "verification_transition":
        governed_family = rec.get("governed_family", "")
        from_state = rec.get("from_state", "")
        to_state = rec.get("to_state", "")
        summary = f"{governed_family}: {from_state} \u2192 {to_state}"
        detail = {
            "from_state": from_state,
            "to_state": to_state,
            "governed_family": governed_family,
        }
        evidence = {
            "event_id": rec.get("event_id", ""),
            "record_hash": rec.get("record_hash", ""),
        }

    elif category == "opaque_approval":
        artifact_identity = rec.get("artifact_identity", "")
        governed_family = rec.get("governed_family", "")
        prefix = _artifact_identity_prefix(artifact_identity)
        summary = f"approve {prefix} for {governed_family}"
        detail = {
            "artifact_identity": artifact_identity,
            "operator": rec.get("approving_operator", ""),
            "governed_family": governed_family,
            "deployment_context": rec.get("deployment_context", ""),
            "policy_version": rec.get("policy_version", ""),
        }
        evidence = {
            "event_id": rec.get("event_id", ""),
            "record_hash": rec.get("record_hash", ""),
        }

    elif category == "opaque_revocation":
        artifact_identity = rec.get("artifact_identity", "")
        governed_family = rec.get("governed_family", "")
        prefix = _artifact_identity_prefix(artifact_identity)
        summary = f"revoke {prefix} for {governed_family}"
        detail = {
            "artifact_identity": artifact_identity,
            "operator": rec.get("revoking_operator", ""),
            "governed_family": governed_family,
            "deployment_context": rec.get("deployment_context", ""),
            "policy_version": rec.get("policy_version", ""),
        }
        evidence = {
            "event_id": rec.get("event_id", ""),
            "record_hash": rec.get("record_hash", ""),
        }

    elif category == "opaque_invocation_decision":
        artifact_identity = rec.get("artifact_identity", "")
        resolution = rec.get("resolution", "")
        governed_family = rec.get("governed_family", "")
        summary = f"opaque invocation \u2192 {resolution}"
        detail = {
            "artifact_identity": artifact_identity,
            "resolution": resolution,
            "governed_family": governed_family,
        }
        evidence = {
            "event_id": rec.get("event_id", ""),
            "record_hash": rec.get("record_hash", ""),
        }

    elif category == "ungoverned_observation":
        op_type = rec.get("operation_type", "")
        target = rec.get("target", "")
        source = rec.get("source", "")
        summary = f"ungoverned {op_type}" + (f" on {target}" if target else "")
        detail = {
            "operation_type": op_type,
            "target": target,
            "source": source,
        }
        evidence = {
            "event_id": rec.get("event_id", ""),
            "record_hash": rec.get("record_hash", ""),
        }

    entry = {
        "sequence_position": sequence_position,
        "timestamp_utc": rec.get("timestamp_utc", ""),
        "event_category": category,
        "governed_family": governed_family,
        "summary": summary,
        "evidence": evidence,
        "detail": detail,
    }

    # Propagate user_identity when present on the chain record.
    uid = rec.get("user_identity", "")
    if uid:
        entry["user_identity"] = uid

    return entry


# Map from classifier action_type to hook operation_type for dedup matching.
_ACTION_TO_OP = {
    "read": {"read"},
    "write": {"write", "edit"},
    "list": {"list", "glob", "grep"},
    "execute": {"execute"},
    "delete": {"delete"},
    "network": {"execute"},
}


def _parse_ts(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 UTC timestamp, returning None on failure."""
    try:
        s = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, AttributeError):
        return None


def _deduplicate_proxy_and_hook(entries: list[dict]) -> list[dict]:
    """Remove ungoverned observations that duplicate a nearby mediated decision.

    When the API proxy is active, both the proxy and the hook record the same
    tool call. The proxy's mediated decision (pre-execution) is authoritative;
    the hook's observation (post-execution) is redundant.

    Match criteria: same target, action type compatible, within 10 seconds.
    """
    # Build an index of mediated decision targets with parsed timestamps.
    mediated: list[tuple[str, str, Optional[datetime]]] = []
    for e in entries:
        if e["event_category"] == "action_decision":
            target = e["detail"].get("target", "")
            action_type = e["detail"].get("action_type", "")
            ts = _parse_ts(e["timestamp_utc"])
            if target:
                mediated.append((target, action_type, ts))

    if not mediated:
        return entries

    def _is_duplicate_observation(entry: dict) -> bool:
        if entry["event_category"] != "ungoverned_observation":
            return False
        obs_target = entry["detail"].get("target", "")
        obs_op = entry["detail"].get("operation_type", "")
        if not obs_target:
            return False
        obs_ts = _parse_ts(entry["timestamp_utc"])
        for m_target, m_action, m_ts in mediated:
            if obs_target != m_target:
                continue
            # Check action type compatibility
            compatible_ops = _ACTION_TO_OP.get(m_action, set())
            if obs_op and obs_op not in compatible_ops:
                continue
            # Check timestamp proximity (within 10 seconds)
            if obs_ts is not None and m_ts is not None:
                delta = abs((obs_ts - m_ts).total_seconds())
                if delta <= 10:
                    return True
            else:
                # Cannot compare timestamps — match on target alone
                return True
        return False

    return [e for e in entries if not _is_duplicate_observation(e)]


def governance_activity_view(
    chain_path: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    governed_family: Optional[str] = None,
    event_category: Optional[str] = None,
    resolution: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    policy_decision: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> dict:
    """Assemble a Governance Activity Projection (GAP).

    Returns a bounded, filtered, evidence-linked view over recent
    governance-significant events from the decision chain.

    Events are returned in reverse chronological order (most recent first).
    """
    rows = load_chain_rows(chain_path)

    # Normalize all rows into activity entries with 1-based sequence positions.
    entries: list[dict] = []
    for i, rec in enumerate(rows):
        entry = _normalize_activity_entry(rec, sequence_position=i + 1)
        if entry is not None:
            entries.append(entry)

    # Deduplicate: suppress ungoverned observations that overlap with a
    # nearby mediated decision (same target, within a short time window).
    # When the API proxy governs pre-execution, the hook's post-execution
    # observation of the same operation is redundant.
    entries = _deduplicate_proxy_and_hook(entries)

    # Apply filters (conjunctive).
    if governed_family:
        entries = [e for e in entries if e["governed_family"] == governed_family]
    if event_category:
        entries = [e for e in entries if e["event_category"] == event_category]
    if resolution:
        entries = [
            e for e in entries
            if e["event_category"] == "opaque_invocation_decision"
            and e["detail"].get("resolution") == resolution
        ]
    if start_time:
        entries = [e for e in entries if e["timestamp_utc"] >= start_time]
    if end_time:
        entries = [e for e in entries if e["timestamp_utc"] <= end_time]
    if policy_decision:
        entries = [
            e for e in entries
            if e["detail"].get("policy_decision", "") == policy_decision
        ]
    if tool_name:
        entries = [
            e for e in entries
            if e["detail"].get("tool_name", "") == tool_name
        ]

    # Reverse chronological order (most recent first).
    entries.reverse()

    total_matching = len(entries)

    # Compute summary counts over the filtered set (before pagination).
    allow_count = sum(
        1 for e in entries
        if e["detail"].get("policy_decision") == "ALLOW"
    )
    deny_count = sum(
        1 for e in entries
        if e["detail"].get("policy_decision") == "DENY"
    )
    tool_categories = len({
        e["detail"].get("tool_name", "")
        for e in entries
        if e["detail"].get("tool_name")
    })

    # Apply window controls.
    if offset > 0:
        entries = entries[offset:]
    entries = entries[:limit]

    return {
        "timestamp_utc": _now_utc_z(),
        "entries": entries,
        "total_matching": total_matching,
        "chain_event_count": len(rows),
        "summary": {
            "allow_count": allow_count,
            "deny_count": deny_count,
            "tool_categories": tool_categories,
        },
        "window": {
            "limit": limit,
            "offset": offset,
        },
        "filters": {
            "governed_family": governed_family,
            "event_category": event_category,
            "resolution": resolution,
            "start_time": start_time,
            "end_time": end_time,
            "policy_decision": policy_decision,
            "tool_name": tool_name,
        },
    }


# ---------------------------------------------------------------------------
# Transparency metric
# ---------------------------------------------------------------------------


def compute_transparency_metric(
    rows: list[dict],
    *,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> dict:
    """Compute the transparency metric from chain rows.

    Transparency = governed_operations / (governed_operations + ungoverned_observations).
    If no ungoverned observations exist, returns observation_data=False so the
    dashboard can show "No observation data" instead of a misleading 100%.
    """
    governed_count = 0
    ungoverned_count = 0

    for row in rows:
        ts = row.get("timestamp_utc", "")
        if not _in_time_range(ts, start_time, end_time):
            continue
        event_type = row.get("event_type")
        if event_type == "ungoverned_operation_observed":
            ungoverned_count += 1
        elif event_type is None:
            # Action records (governed operations) have no event_type field
            governed_count += 1

    has_observation_data = ungoverned_count > 0
    total = governed_count + ungoverned_count

    if total == 0:
        transparency_pct = None
    else:
        transparency_pct = round(governed_count / total, 6)

    return {
        "observation_data": has_observation_data,
        "governed_operations": governed_count,
        "ungoverned_observations": ungoverned_count,
        "total_observed": total,
        "transparency_pct": transparency_pct,
    }


# ---------------------------------------------------------------------------
# Audit Query and Report Functions
# ---------------------------------------------------------------------------


def _load_sidecar_records(records_dir: Path) -> list[dict]:
    """Load all sidecar .record.json files from the records directory."""
    if not records_dir.exists():
        return []
    records = []
    for rfile in sorted(records_dir.glob("*.record.json")):
        try:
            rec = json.loads(rfile.read_text(encoding="utf-8"))
            records.append(rec)
        except (json.JSONDecodeError, OSError):
            continue
    return records


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 UTC timestamp string."""
    if not ts:
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None


def _in_time_range(
    ts_str: str,
    start: Optional[str],
    end: Optional[str],
) -> bool:
    """Check if a timestamp falls within the given range (inclusive)."""
    if not start and not end:
        return True
    ts = _parse_timestamp(ts_str)
    if ts is None:
        return False
    if start:
        ts_start = _parse_timestamp(start)
        if ts_start and ts < ts_start:
            return False
    if end:
        ts_end = _parse_timestamp(end)
        if ts_end and ts > ts_end:
            return False
    return True


def audit_query(
    chain_path: Path,
    records_dir: Path,
    *,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user_identity: Optional[str] = None,
    tool_name: Optional[str] = None,
    policy_decision: Optional[str] = None,
    event_category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Query the governance chain with filters for audit purposes.

    Supports filtering by time range, user, tool, policy decision, and
    event category. Returns matching entries in reverse chronological order.
    """
    rows = load_chain_rows(chain_path)
    sidecar_by_request_id: dict[str, dict] = {}
    for rec in _load_sidecar_records(records_dir):
        rid = rec.get("request_id")
        if rid:
            sidecar_by_request_id[rid] = rec

    entries: list[dict] = []
    for i, rec in enumerate(rows):
        entry = _normalize_activity_entry(rec, sequence_position=i + 1)
        if entry is None:
            continue

        # Time range filter
        if not _in_time_range(entry["timestamp_utc"], start_time, end_time):
            continue

        # User filter: check chain record and sidecar
        if user_identity:
            rec_user = rec.get("user_identity", "")
            sidecar = sidecar_by_request_id.get(rec.get("request_id", ""), {})
            sidecar_user = sidecar.get("user_identity", "")
            if user_identity not in (rec_user, sidecar_user):
                continue

        # Tool filter (check original_tool for v2 records too)
        if tool_name:
            rec_tool = rec.get("tool", rec.get("capability_class", ""))
            rec_original = rec.get("original_tool", "")
            if rec_tool != tool_name and rec_original != tool_name:
                continue

        # Policy decision filter
        if policy_decision:
            rec_decision = rec.get("policy_decision", "")
            if rec_decision != policy_decision:
                continue

        # Event category filter
        if event_category:
            if entry["event_category"] != event_category:
                continue

        # Enrich with sidecar user_identity if available
        sidecar = sidecar_by_request_id.get(rec.get("request_id", ""), {})
        if sidecar.get("user_identity"):
            entry["user_identity"] = sidecar["user_identity"]
        elif rec.get("user_identity"):
            entry["user_identity"] = rec["user_identity"]

        entries.append(entry)

    # Deduplicate: suppress ungoverned observations that overlap with a
    # nearby mediated decision (same operation recorded by both proxy and hook).
    entries = _deduplicate_proxy_and_hook(entries)

    entries.reverse()
    total_matching = len(entries)

    if offset > 0:
        entries = entries[offset:]
    entries = entries[:limit]

    return {
        "timestamp_utc": _now_utc_z(),
        "entries": entries,
        "total_matching": total_matching,
        "chain_event_count": len(rows),
        "window": {"limit": limit, "offset": offset},
        "filters": {
            "start_time": start_time,
            "end_time": end_time,
            "user_identity": user_identity,
            "tool_name": tool_name,
            "policy_decision": policy_decision,
            "event_category": event_category,
        },
    }


def audit_record_detail(
    chain_path: Path,
    records_dir: Path,
    *,
    record_id: str,
) -> dict:
    """Retrieve a single governance record by request_id, event_id, or record_hash.

    Returns the full chain record plus any matching sidecar record.
    """
    rows = load_chain_rows(chain_path)
    match: Optional[dict] = None
    for rec in rows:
        if record_id in (
            rec.get("request_id", ""),
            rec.get("event_id", ""),
            rec.get("record_hash", ""),
        ):
            match = rec
            break

    if match is None:
        return {"found": False, "record_id": record_id}

    sidecar: Optional[dict] = None
    rid = match.get("request_id")
    if rid and records_dir.exists():
        sidecar_path = records_dir / f"{rid}.record.json"
        if sidecar_path.exists():
            try:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    return {
        "found": True,
        "record_id": record_id,
        "chain_record": match,
        "sidecar_record": sidecar,
    }


def audit_report(
    chain_path: Path,
    records_dir: Path,
    *,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    group_by: str = "tool",
) -> dict:
    """Generate an audit summary report over a time period.

    group_by: "tool", "user", "decision", or "category".
    Returns counts grouped by the specified dimension.
    """
    rows = load_chain_rows(chain_path)
    sidecar_by_request_id: dict[str, dict] = {}
    for rec in _load_sidecar_records(records_dir):
        rid = rec.get("request_id")
        if rid:
            sidecar_by_request_id[rid] = rec

    groups: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    total = 0

    for rec in rows:
        ts = rec.get("timestamp_utc", "")
        if not _in_time_range(ts, start_time, end_time):
            continue
        total += 1

        pd = rec.get("policy_decision", "")
        if pd:
            decision_counts[pd] += 1

        if group_by == "tool":
            key = rec.get("tool", rec.get("capability_class", ""))
            event_type = rec.get("event_type", "")
            if not key and event_type:
                key = event_type
            groups[key or "unknown"] += 1

        elif group_by == "user":
            uid = rec.get("user_identity", "")
            if not uid:
                sidecar = sidecar_by_request_id.get(rec.get("request_id", ""), {})
                uid = sidecar.get("user_identity", "")
            groups[uid or "anonymous"] += 1

        elif group_by == "decision":
            key = rec.get("policy_decision", "")
            event_type = rec.get("event_type", "")
            if not key and event_type:
                key = event_type
            groups[key or "event"] += 1

        elif group_by == "category":
            entry = _normalize_activity_entry(rec, sequence_position=0)
            cat = entry["event_category"] if entry else "unknown"
            groups[cat] += 1

    return {
        "timestamp_utc": _now_utc_z(),
        "report_type": "audit_summary",
        "group_by": group_by,
        "time_range": {"start": start_time, "end": end_time},
        "total_records": total,
        "decision_summary": dict(decision_counts.most_common()),
        "groups": [
            {"key": k, "count": v} for k, v in groups.most_common()
        ],
    }
