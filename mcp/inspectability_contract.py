from __future__ import annotations

from pathlib import Path
from typing import Any

from storage_contract import describe_storage_contract
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt
from tool_event_store import get_tool_event_by_digest, list_tool_events_for_receipt

INSPECTABILITY_CONTRACT_VERSION = "govmcp_inspectability_contract_v1"
SELECTED_SEAM = "receipt_linked_inspectability_query_consistency"

CONSTITUTIVE_SURFACES = [
    "capabilities.receipt",
    "capabilities.replay_check",
    "capabilities.receipt_tool_events",
    "capabilities.tool_event_receipts",
    "capabilities.tool_event_list_for_receipt",
]

PARTIAL_SURFACES = [
    "capabilities.list_recent",
    "capabilities.tool_event_list_recent",
]


def canonical_tool_event_digests(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    clean = {
        str(item or "").strip()
        for item in value
        if isinstance(item, str) and len(item) == 71 and item.startswith("sha256:")
    }
    return sorted(clean)


def describe_inspectability_contract(query_surface: str, query_scope: str) -> dict[str, Any]:
    return {
        "version": INSPECTABILITY_CONTRACT_VERSION,
        "selected_seam": SELECTED_SEAM,
        "query_surface": query_surface,
        "query_scope": query_scope,
        "constitutive_surfaces": CONSTITUTIVE_SURFACES,
        "partial_surfaces": PARTIAL_SURFACES,
        "minimum_path_preserved": True,
    }


def build_receipt_payload(
    *,
    repo_root: Path,
    run_id: str,
    digest: str,
    action_record: dict[str, Any],
    digest_valid: bool,
    signature_present: bool,
    signature_valid: bool,
    signature_reason_token: str,
) -> dict[str, Any]:
    tool_event_digests = canonical_tool_event_digests(action_record.get("tool_event_digests", []))
    return {
        "receipt_version": "v0",
        "run_id": run_id,
        "digest": digest,
        "action_record": action_record,
        "tool_event_digests": tool_event_digests,
        "linked_tool_event_count": len(tool_event_digests),
        "digest_valid": bool(digest_valid),
        "signature_present": bool(signature_present),
        "signature_valid": bool(signature_valid),
        "signature_reason_token": str(signature_reason_token or "NONE"),
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.receipt", "constitutive"
        ),
    }


def build_recent_receipts_payload(
    repo_root: Path,
    rows: list[dict[str, Any]],
    linked_counts: dict[str, int],
) -> dict[str, Any]:
    receipts = []
    for row in rows:
        run_id = str(row.get("run_id", ""))
        receipts.append(
            {
                "run_id": run_id,
                "digest": str(row.get("digest", "")),
                "action_name": str(row.get("action_name", "")),
                "outcome": str(row.get("outcome", "")),
                "linked_tool_event_count": int(linked_counts.get(run_id, 0)),
                "query_scope": "partial",
            }
        )
    return {
        "receipt_version": "v0",
        "receipts": receipts,
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.list_recent", "partial"
        ),
    }


def build_replay_payload(
    *,
    repo_root: Path,
    run_id: str,
    digest: str,
    digest_valid: bool,
    admissible_now: bool,
    reason_token: str,
    action_name: str,
    normalized_params: dict[str, Any],
    signature_present: bool,
    signature_valid: bool,
    signature_reason_token: str,
    tool_event_digests: list[str],
    policy_context_used: str,
) -> dict[str, Any]:
    clean_digests = canonical_tool_event_digests(tool_event_digests)
    return {
        "replay_version": "v0",
        "run_id": run_id,
        "digest": digest,
        "digest_valid": bool(digest_valid),
        "admissible_now": bool(admissible_now),
        "reason_token": str(reason_token or "UNKNOWN"),
        "action_name": str(action_name or ""),
        "normalized_params": normalized_params,
        "signature_present": bool(signature_present),
        "signature_valid": bool(signature_valid),
        "signature_reason_token": str(signature_reason_token or "NONE"),
        "tool_event_digests": clean_digests,
        "linked_tool_event_count": len(clean_digests),
        "policy_context_used": str(policy_context_used or "DEFAULT"),
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.replay_check", "constitutive"
        ),
    }


def build_receipt_tool_events_payload(repo_root: Path, receipt_id: str, digests: list[str], policy_context: str) -> dict[str, Any]:
    clean_digests = canonical_tool_event_digests(digests)
    return {
        "tool_event_link_version": "v0",
        "receipt_id": str(receipt_id or "").strip(),
        "tool_event_digests": clean_digests,
        "linked_tool_event_count": len(clean_digests),
        "policy_context_used": str(policy_context or "DEFAULT"),
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.receipt_tool_events", "constitutive"
        ),
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


def build_tool_event_receipts_payload(repo_root: Path, digest: str, receipt_ids: list[str], policy_context: str) -> dict[str, Any]:
    clean_receipts = sorted({str(item or "").strip() for item in receipt_ids if str(item or "").strip()})
    return {
        "tool_event_link_version": "v0",
        "tool_event_digest": str(digest or "").strip(),
        "receipt_ids": clean_receipts,
        "linked_receipt_count": len(clean_receipts),
        "policy_context_used": str(policy_context or "DEFAULT"),
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.tool_event_receipts", "constitutive"
        ),
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


def build_tool_event_row_payload(row: dict[str, Any], resolution_state: str = "RESOLVED") -> dict[str, Any]:
    ref = str(row.get("tool_event_ref", ""))
    payload_digest = str(row.get("tool_event_digest", ""))
    return {
        "tool_event_digest": payload_digest,
        "tool_event_payload_sha256": payload_digest,
        "tool_event_ref": ref,
        "receipt_id": str(row.get("receipt_id", "")),
        "stored_at": int(row.get("stored_seq", 0)),
        "resolution_state": resolution_state,
    }


def resolve_tool_event_rows_for_receipt(repo_root: Path, receipt_id: str) -> list[dict[str, Any]]:
    rid = str(receipt_id or "").strip()
    runtime_rows = list_tool_events_for_receipt(repo_root, rid)
    runtime_by_digest = {
        str(row.get("tool_event_digest", "")).strip(): row for row in runtime_rows if isinstance(row, dict)
    }
    resolved: list[dict[str, Any]] = []
    for digest in get_tool_events_for_receipt(repo_root, rid):
        row = runtime_by_digest.get(digest)
        if row is None:
            row = get_tool_event_by_digest(repo_root, digest)
        if isinstance(row, dict):
            resolved.append(build_tool_event_row_payload(row, "RESOLVED"))
        else:
            resolved.append(
                build_tool_event_row_payload(
                    {
                        "tool_event_digest": digest,
                        "tool_event_ref": "",
                        "receipt_id": rid,
                        "stored_seq": 0,
                    },
                    "INDEX_ONLY",
                )
            )
    return resolved


def build_tool_event_list_for_receipt_payload(repo_root: Path, receipt_id: str, policy_context: str) -> dict[str, Any]:
    rid = str(receipt_id or "").strip()
    events = resolve_tool_event_rows_for_receipt(repo_root, rid)
    return {
        "tool_event_version": "v0",
        "receipt_id": rid,
        "events": events,
        "linked_tool_event_count": len(events),
        "policy_context_used": str(policy_context or "DEFAULT"),
        "storage_contract": describe_storage_contract(repo_root),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.tool_event_list_for_receipt", "constitutive"
        ),
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


def build_tool_event_list_recent_payload(repo_root: Path, rows: list[dict[str, Any]], policy_context: str) -> dict[str, Any]:
    events = [build_tool_event_row_payload(r, "RESOLVED") for r in rows]
    return {
        "tool_event_version": "v0",
        "events": events,
        "policy_context_used": str(policy_context or "DEFAULT"),
        "inspectability_contract": describe_inspectability_contract(
            "capabilities.tool_event_list_recent", "partial"
        ),
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }
