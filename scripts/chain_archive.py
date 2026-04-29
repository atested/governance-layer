"""Archive support for preserved governance chains."""

from __future__ import annotations

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
) -> dict[str, Any]:
    """Preserve the current chain and write an archive manifest.

    If the chain is missing, the manifest still records the terminal condition
    as a sidecar-only archive event.
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
    return manifest


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
