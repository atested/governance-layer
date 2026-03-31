#!/usr/bin/env python3
"""
readout.py — Governed Action Status Record assembly and Governance Activity
Projection for operator readout.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from approval_store import ApprovalStore, load_approval_store_from_chain
from verification import VerificationStateTracker, load_verification_state_from_chain


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


def check_chain_integrity(chain_path: Path) -> dict:
    if not chain_path.exists():
        return {"status": "ok", "checked": False, "chain_event_count": 0}

    verify_record_mod = _load_verify_record_module()
    prev_hash: Optional[str] = None
    line_no = 0
    with open(chain_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            line_no += 1
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                return {"status": "broken", "broken_at": f"line:{line_no}", "reason": "invalid_json"}

            rc, lines = verify_record_mod.verify_record_dict(rec)
            if rc != 0:
                return {
                    "status": "broken",
                    "broken_at": rec.get("event_id") or rec.get("request_id") or f"line:{line_no}",
                    "reason": lines[0].replace("FAIL: ", "") if lines else "record_verification_failed",
                }

            link = rec.get("prev_record_hash")
            if line_no > 1 and "prev_record_hash" in rec and link != prev_hash:
                return {
                    "status": "broken",
                    "broken_at": rec.get("event_id") or rec.get("request_id") or f"line:{line_no}",
                    "reason": "prev_record_hash_mismatch",
                }

            prev_hash = rec.get("record_hash")

    return {"status": "ok", "checked": True, "chain_event_count": line_no}


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
        load_verification_state_from_chain(str(chain_path)).all_states() if chain_path.exists() else {}
    )
    reconstructed_approval_store = (
        load_approval_store_from_chain(str(chain_path)) if chain_path.exists() else ApprovalStore()
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
])

_EVENT_TYPE_TO_CATEGORY = {
    "verification_state_transition": "verification_transition",
    "opaque_artifact_approval": "opaque_approval",
    "opaque_artifact_revocation": "opaque_revocation",
    "opaque_invocation_decision": "opaque_invocation_decision",
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
        tool_name = rec.get("tool", rec.get("capability_class", "unknown"))
        policy_decision = rec.get("policy_decision", "unknown")
        record_type = rec.get("record_type", "")
        governed_family = rec.get("governed_family", "")
        summary = f"{tool_name} \u2192 {policy_decision}"
        detail = {
            "tool_name": tool_name,
            "policy_decision": policy_decision,
            "record_type": record_type,
            "verification_state": rec.get("verification_state", ""),
        }
        evidence = {
            "request_id": rec.get("request_id", ""),
            "record_hash": rec.get("record_hash", ""),
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

    return {
        "sequence_position": sequence_position,
        "timestamp_utc": rec.get("timestamp_utc", ""),
        "event_category": category,
        "governed_family": governed_family,
        "summary": summary,
        "evidence": evidence,
        "detail": detail,
    }


def governance_activity_view(
    chain_path: Path,
    *,
    limit: int = 50,
    offset: int = 0,
    governed_family: Optional[str] = None,
    event_category: Optional[str] = None,
    resolution: Optional[str] = None,
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

    # Reverse chronological order (most recent first).
    entries.reverse()

    total_matching = len(entries)

    # Apply window controls.
    if offset > 0:
        entries = entries[offset:]
    entries = entries[:limit]

    return {
        "timestamp_utc": _now_utc_z(),
        "entries": entries,
        "total_matching": total_matching,
        "chain_event_count": len(rows),
        "window": {
            "limit": limit,
            "offset": offset,
        },
        "filters": {
            "governed_family": governed_family,
            "event_category": event_category,
            "resolution": resolution,
        },
    }
