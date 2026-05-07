#!/usr/bin/env python3
"""Layer 3 unified multi-machine readout helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    from machine_identity import load_machine_identity, load_machine_registry
    from remote_import import sha256_bytes, verify_stored_segment_binding
    from storage_contract import runtime_root
except ImportError:  # pragma: no cover - package import path
    from scripts.machine_identity import load_machine_identity, load_machine_registry
    from scripts.remote_import import sha256_bytes, verify_stored_segment_binding
    from scripts.storage_contract import runtime_root


PRIMARY_ONLY = "primary"
ALL_MACHINES = "all"


def normalize_machine_ids(machine_ids: Optional[str | list[str] | tuple[str, ...] | set[str]]) -> Optional[set[str]]:
    if machine_ids is None:
        return None
    if isinstance(machine_ids, str):
        raw = [part.strip() for part in machine_ids.split(",")]
    else:
        raw = [str(part).strip() for part in machine_ids]
    values = {part for part in raw if part and part.lower() not in {ALL_MACHINES, "*"}}
    return values or None


def load_unified_records(
    repo_root: Path,
    chain_path: Path,
    *,
    machine_scope: str = ALL_MACHINES,
    machine_ids: Optional[str | list[str] | tuple[str, ...] | set[str]] = None,
    include_import_envelopes: bool = True,
) -> tuple[list[dict], dict]:
    """Return primary-local records plus verified imported remote records.

    Remote records are copied from JSONL sidecars referenced by successful
    import envelope records. Each remote record is annotated with import
    metadata but its original hash/signature fields are preserved.
    """
    scope = _normalize_scope(machine_scope)
    selected = normalize_machine_ids(machine_ids)
    primary_identity = load_machine_identity(repo_root) or {}
    primary_machine_id = primary_identity.get("machine_id")

    primary_rows = _load_jsonl(chain_path)
    envelopes = [
        row for row in primary_rows
        if row.get("event_type") == "remote_chain_import"
        and row.get("verification_result") == "PASS"
    ]

    envelope_sequences = {
        row.get("record_hash"): sequence
        for sequence, row in enumerate(primary_rows, start=1)
        if row.get("event_type") == "remote_chain_import"
    }

    records: list[dict] = []
    for sequence, row in enumerate(primary_rows, start=1):
        if row.get("event_type") == "remote_chain_import" and not include_import_envelopes:
            continue
        if _record_selected(row, scope, selected, primary_machine_id, is_imported=False):
            annotated = dict(row)
            annotated.setdefault("event_timestamp_utc", annotated.get("timestamp_utc", ""))
            annotated.setdefault("primary_import_timestamp_utc", None)
            annotated["_unified_source"] = "primary_chain"
            annotated["_unified_sequence"] = sequence
            annotated["_unified_sort_order"] = sequence * 1_000_000_000
            records.append(annotated)

    imported_count = 0
    sidecars: list[dict] = []
    for envelope in envelopes:
        ok, error = verify_stored_segment_binding(repo_root, envelope)
        if not ok:
            continue
        rel = envelope.get("stored_segment_path")
        sidecar_path = runtime_root(repo_root) / str(rel)
        raw = sidecar_path.read_bytes()
        sidecar_meta = {
            "source_machine_id": envelope.get("source_machine_id"),
            "segment_id": envelope.get("segment_id"),
            "stored_segment_path": rel,
            "stored_segment_sha256": envelope.get("stored_segment_sha256"),
            "actual_segment_sha256": sha256_bytes(raw),
            "remote_first_record_hash": envelope.get("remote_first_record_hash"),
            "remote_last_record_hash": envelope.get("remote_last_record_hash"),
            "remote_record_count": envelope.get("remote_record_count"),
            "import_envelope_hash": envelope.get("record_hash"),
            "import_sequence": envelope.get("import_sequence"),
            "primary_import_timestamp_utc": envelope.get("primary_import_timestamp_utc"),
            "binding_error": error,
        }
        sidecars.append(sidecar_meta)
        envelope_sequence = envelope_sequences.get(envelope.get("record_hash"), 0)
        for index, record in enumerate(_loads_jsonl_bytes(raw), start=1):
            if not _record_selected(record, scope, selected, primary_machine_id, is_imported=True):
                continue
            annotated = dict(record)
            annotated.setdefault("machine_id", envelope.get("source_machine_id"))
            annotated.setdefault("machine_role", "remote")
            annotated.setdefault("event_timestamp_utc", annotated.get("timestamp_utc", ""))
            annotated["primary_import_timestamp_utc"] = envelope.get("primary_import_timestamp_utc")
            annotated["import_envelope_hash"] = envelope.get("record_hash")
            annotated["import_sequence"] = envelope.get("import_sequence")
            annotated["segment_id"] = envelope.get("segment_id")
            annotated["stored_segment_sha256"] = envelope.get("stored_segment_sha256")
            annotated["_unified_source"] = "remote_import"
            annotated["_unified_sequence"] = f"import:{envelope.get('import_sequence')}:{index}"
            annotated["_unified_sort_order"] = envelope_sequence * 1_000_000_000 + index
            records.append(annotated)
            imported_count += 1

    records.sort(key=_unified_sort_key)
    context = {
        "machine_scope": scope,
        "machine_ids": sorted(selected) if selected else [],
        "primary_machine_id": primary_machine_id,
        "primary_record_count": sum(1 for row in records if row.get("_unified_source") == "primary_chain"),
        "imported_record_count": imported_count,
        "import_envelopes": envelopes,
        "sidecars": sidecars,
        "machine_registry": load_machine_registry(repo_root) or {},
    }
    return records, context


def selected_import_context(
    repo_root: Path,
    selected_records: list[dict],
) -> dict:
    envelope_hashes = {
        record.get("import_envelope_hash")
        for record in selected_records
        if isinstance(record.get("import_envelope_hash"), str)
    }
    _records, context = load_unified_records(repo_root, runtime_root(repo_root) / "LOGS" / "decision-chain.jsonl")
    envelopes = [
        envelope for envelope in context["import_envelopes"]
        if envelope.get("record_hash") in envelope_hashes
    ]
    sidecars = [
        sidecar for sidecar in context["sidecars"]
        if sidecar.get("import_envelope_hash") in envelope_hashes
    ]
    return {
        "machine_registry_snapshot": context["machine_registry"],
        "import_envelopes": envelopes,
        "remote_sidecar_hashes": sidecars,
    }


def _record_selected(
    record: dict,
    scope: str,
    selected: Optional[set[str]],
    primary_machine_id: Optional[str],
    *,
    is_imported: bool,
) -> bool:
    machine_id = record.get("machine_id")
    role = record.get("machine_role")
    if selected is not None:
        return machine_id in selected
    if scope == PRIMARY_ONLY:
        return not is_imported
    return True


def _normalize_scope(scope: Optional[str]) -> str:
    value = str(scope or ALL_MACHINES).strip().lower()
    if value in {"primary", "primary_only", "local"}:
        return PRIMARY_ONLY
    return ALL_MACHINES


def _unified_sort_key(record: dict) -> tuple[int, str]:
    try:
        order = int(record.get("_unified_sort_order") or 0)
    except (TypeError, ValueError):
        order = 0
    seq = str(record.get("_unified_sequence") or "")
    return order, seq


def _load_jsonl(path: Path) -> list[dict]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    return _loads_jsonl_bytes(raw)


def _loads_jsonl_bytes(raw: bytes) -> list[dict]:
    records: list[dict] = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records
