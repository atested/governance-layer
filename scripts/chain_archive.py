"""Archive support for preserved governance chains."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ARCHIVE_MANIFEST_VERSION = 1


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def archive_root_for(chain_path: Path) -> Path:
    return chain_path.parent / "archive"


def archive_manifest_path(chain_path: Path, archive_id: str) -> Path:
    return archive_root_for(chain_path) / f"{archive_id}.manifest.json"


def list_archives(chain_path: Path) -> list[dict[str, Any]]:
    root = archive_root_for(chain_path)
    if not root.exists():
        return []
    manifests: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.manifest.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            data.setdefault("manifest_path", str(path))
            manifests.append(data)
    return manifests


def get_archive_manifest(chain_path: Path, archive_id: str) -> Optional[dict[str, Any]]:
    safe_id = _safe_archive_id(archive_id)
    path = archive_manifest_path(chain_path, safe_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None
    return data if isinstance(data, dict) else None


def archive_chain(
    chain_path: Path,
    *,
    reason: str,
    payload: Optional[dict[str, Any]] = None,
    sidecar_events_path: Optional[Path] = None,
    write_genesis: bool = True,
    signing_key: Any = None,
    signing_key_id: Optional[str] = None,
    genesis_extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Preserve the current chain and write an archive manifest.

    If the chain is missing, the manifest still records the terminal condition
    as a sidecar-only archive event.

    When the chain existed and ``write_genesis`` is true (the default), the
    archived chain is replaced with a fresh chain whose only record is a
    ``chain_started_after_archive`` provenance record (see
    :func:`write_chain_genesis`). The chain is therefore never left missing,
    which is what previously crash-looped the Rust quality service on the QA
    chain: a missing/empty file gave the restarted writer nothing to link to.

    Callers that write their own genesis (the proxy, which signs the
    decision-chain genesis with full request context) pass
    ``write_genesis=False`` and append the genesis themselves afterwards.
    Pass ``signing_key``/``signing_key_id`` to sign the genesis with the
    chain's own key (the decision key for the decision chain, the QA key for
    the QA chain) so the genesis is consistent with the records that follow.
    """

    payload = dict(payload or {})
    root = archive_root_for(chain_path)
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_id = f"chain-archive-{ts}-{os.getpid()}"
    archive_chain_path = root / f"{archive_id}.jsonl"
    manifest_path = archive_manifest_path(chain_path, archive_id)
    suffix = 1
    while archive_chain_path.exists() or manifest_path.exists():
        archive_id = f"chain-archive-{ts}-{os.getpid()}-{suffix}"
        archive_chain_path = root / f"{archive_id}.jsonl"
        manifest_path = archive_manifest_path(chain_path, archive_id)
        suffix += 1
    existed = chain_path.exists()
    record_count = _count_records(chain_path) if existed else 0
    last_hash = _last_hash(chain_path) if existed else None
    last_sequence = _last_sequence(chain_path) if existed else 0

    if existed:
        shutil.move(str(chain_path), str(archive_chain_path))

    manifest = {
        "schema_version": ARCHIVE_MANIFEST_VERSION,
        "archive_id": archive_id,
        "archived_at_utc": now_utc_z(),
        "reason": reason,
        "payload": payload,
        "original_chain_path": str(chain_path),
        "archive_chain_path": str(archive_chain_path) if existed else "",
        "chain_existed": existed,
        "record_count": record_count,
        "last_record_hash": last_hash,
        "sidecar_only_terminal_event": True,
        "operator_retention": "Atested never deletes archived chains; the operator manages disk retention.",
    }
    manifest["manifest_path"] = str(manifest_path)
    _write_json(manifest_path, manifest)
    if sidecar_events_path is not None:
        _append_sidecar(sidecar_events_path, "chain_archived_after_integrity_violation", manifest)

    # Replace the moved chain with a single provenance record so the chain is
    # never left missing. Only when the chain actually existed (and was moved):
    # if there was nothing to archive there is no missing-file hazard to repair.
    if write_genesis and existed:
        genesis = write_chain_genesis(
            chain_path,
            manifest=manifest,
            manifest_path=manifest_path,
            prior_chain_last_hash=last_hash,
            prior_sequence=last_sequence,
            signing_key=signing_key,
            signing_key_id=signing_key_id,
            genesis_extra=genesis_extra,
        )
        manifest["genesis_record_hash"] = genesis.get("record_hash")
    return manifest


def write_chain_genesis(
    chain_path: Path,
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    prior_chain_last_hash: Optional[str],
    prior_sequence: int = 0,
    signing_key: Any = None,
    signing_key_id: Optional[str] = None,
    genesis_extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Write a ``chain_started_after_archive`` record as a fresh chain's first line.

    The record documents the provenance of the new chain: the reason the prior
    chain was archived, how many records it held, where the archive manifest
    lives, that manifest's hash, and the prior chain's last record hash. It is
    a registered non-action event, hashed with the shared canonical form so the
    Rust quality service re-verifies the QA-chain genesis identically.

    ``sequence`` continues the prior chain's count (prior + 1) so the QA chain's
    monotonic sequence never moves backwards across an archive.
    """
    # Imported lazily: chain_archive is a low-level utility imported very early
    # by the proxy, and event_model pulls in the policy/identity stack.
    try:
        from event_model import build_non_action_event
    except ImportError:  # pragma: no cover - path-dependent import
        from scripts.event_model import build_non_action_event

    payload: dict[str, Any] = {
        "archive_reason": manifest.get("reason", ""),
        "archived_record_count": manifest.get("record_count", 0),
        "archive_manifest_path": str(manifest_path),
        "archive_manifest_hash": _sha256_file(manifest_path) or "",
        "prior_chain_last_hash": prior_chain_last_hash,
        "archive_id": manifest.get("archive_id", ""),
        "archive_chain_path": manifest.get("archive_chain_path", ""),
        "sequence": int(prior_sequence) + 1,
    }
    if genesis_extra:
        payload.update(genesis_extra)

    genesis = build_non_action_event(
        "chain_started_after_archive",
        payload,
        prev_record_hash=None,
        signing_key=signing_key,
        signing_key_id=signing_key_id,
    )
    line = json.dumps(genesis, sort_keys=True, separators=(",", ":"))
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    with chain_path.open("w", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return genesis


def _safe_archive_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_", "."})


def _count_records(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _last_hash(path: Path) -> Optional[str]:
    last_line = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line.strip()
    except OSError:
        return None
    if not last_line:
        return None
    try:
        rec = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    value = rec.get("record_hash")
    return value if isinstance(value, str) else None


def _last_sequence(path: Path) -> int:
    """Return the sequence of the last record, or 0 if absent/unreadable.

    The QA chain (written by the Rust quality service) carries a monotonic
    ``sequence``. The genesis continues that count so a restart never sees the
    sequence move backwards across an archive.
    """
    last_line = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_line = line.strip()
    except OSError:
        return 0
    if not last_line:
        return 0
    try:
        rec = json.loads(last_line)
    except json.JSONDecodeError:
        return 0
    seq = rec.get("sequence")
    return seq if isinstance(seq, int) and seq >= 0 else 0


def _sha256_file(path: Path) -> Optional[str]:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_sidecar(path: Path, event_type: str, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp_utc": now_utc_z(),
        "event_type": event_type,
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
