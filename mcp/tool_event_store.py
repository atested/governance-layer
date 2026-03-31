from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from storage_contract import runtime_root as contract_runtime_root
from storage_contract import tool_event_bundle_store_root as contract_tool_event_bundle_store_root
from storage_contract import tool_event_store_root as contract_tool_event_store_root

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BUNDLE_ID_RE = re.compile(r"^teb_[0-9a-f]{64}$")
_HEX_PREFIX_RE = re.compile(r"^[0-9a-f]{4,64}$")


def _is_repo_relative_path(ref: str) -> bool:
    token = str(ref or "").strip().replace("\\", "/")
    if not token:
        return False
    path = Path(token)
    if path.is_absolute():
        return False
    parts = [part for part in token.split("/") if part not in ("", ".")]
    return ".." not in parts


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def runtime_root(repo_root: Path) -> Path:
    return contract_runtime_root(repo_root)


def tool_event_store_root(repo_root: Path) -> Path:
    return contract_tool_event_store_root(repo_root)


def _index_path(repo_root: Path) -> Path:
    return tool_event_store_root(repo_root) / "index.v1.json"


def tool_event_bundle_store_root(repo_root: Path) -> Path:
    return contract_tool_event_bundle_store_root(repo_root)


def _bundle_index_path(repo_root: Path) -> Path:
    return tool_event_bundle_store_root(repo_root) / "index.v1.json"


def _clean_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": str(entry.get("receipt_id", "")),
        "run_id": str(entry.get("run_id", "")),
        "stored_seq": int(entry.get("stored_seq", 0)),
        "tool_event_digest": str(entry.get("tool_event_digest", "")),
        "tool_event_ref": str(entry.get("tool_event_ref", "")),
        "action_record_ref": str(entry.get("action_record_ref", "")),
    }


def _valid_entry(entry: dict[str, Any]) -> bool:
    run_id = str(entry.get("run_id", ""))
    digest = str(entry.get("tool_event_digest", ""))
    ref = str(entry.get("tool_event_ref", ""))
    action_ref = str(entry.get("action_record_ref", ""))
    if not _RUN_ID_RE.fullmatch(run_id):
        return False
    if not _DIGEST_RE.fullmatch(digest):
        return False
    if not _is_repo_relative_path(ref):
        return False
    if action_ref and not _is_repo_relative_path(action_ref):
        return False
    return True


def _normalize_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = _clean_entry(row)
        if not _valid_entry(entry):
            continue
        key = (str(entry.get("run_id", "")), str(entry.get("tool_event_digest", "")))
        if key in seen:
            continue
        seen.add(key)
        clean.append(entry)
    clean.sort(key=lambda r: (int(r.get("stored_seq", 0)), str(r.get("run_id", "")), str(r.get("tool_event_digest", ""))))
    for idx, row in enumerate(clean, start=1):
        row["stored_seq"] = idx
        row["receipt_id"] = str(row.get("run_id", ""))
    return clean


def _load_entries(repo_root: Path) -> list[dict[str, Any]]:
    path = _index_path(repo_root)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("entries", [])
    if not isinstance(rows, list):
        return []
    return _normalize_entries(rows)


def _write_entries(repo_root: Path, entries: list[dict[str, Any]]) -> None:
    path = _index_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_event_index_version": "v1",
        "entries": _normalize_entries(entries),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def _clean_bundle_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": str(entry.get("bundle_id", "")),
        "manifest_sha256": str(entry.get("manifest_sha256", "")),
        "tool_event_digests_count": int(entry.get("tool_event_digests_count", 0)),
        "bundle_ref": str(entry.get("bundle_ref", "")),
        "stored_seq": int(entry.get("stored_seq", 0)),
    }


def _valid_bundle_entry(entry: dict[str, Any]) -> bool:
    bundle_id = str(entry.get("bundle_id", ""))
    manifest_sha = str(entry.get("manifest_sha256", ""))
    bundle_ref = str(entry.get("bundle_ref", ""))
    digests_count = int(entry.get("tool_event_digests_count", 0))
    if not _BUNDLE_ID_RE.fullmatch(bundle_id):
        return False
    if not _DIGEST_RE.fullmatch(manifest_sha):
        return False
    if not _is_repo_relative_path(bundle_ref):
        return False
    if digests_count < 0:
        return False
    return True


def _normalize_bundle_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = _clean_bundle_entry(row)
        if not _valid_bundle_entry(entry):
            continue
        key = str(entry.get("bundle_id", ""))
        if key in seen:
            continue
        seen.add(key)
        clean.append(entry)
    clean.sort(key=lambda r: str(r.get("bundle_id", "")))
    for idx, row in enumerate(clean, start=1):
        row["stored_seq"] = idx
    return clean


def _load_bundle_entries(repo_root: Path) -> list[dict[str, Any]]:
    path = _bundle_index_path(repo_root)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("entries", [])
    if not isinstance(rows, list):
        return []
    return _normalize_bundle_entries(rows)


def _write_bundle_entries(repo_root: Path, entries: list[dict[str, Any]]) -> None:
    path = _bundle_index_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tool_event_bundle_index_version": "v1", "entries": _normalize_bundle_entries(entries)}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def upsert_tool_event_index(
    repo_root: Path,
    run_id: str,
    tool_event_digest: str,
    tool_event_ref: str,
    action_record_ref: str,
) -> dict[str, Any]:
    prev = _load_entries(repo_root)
    collision = False
    for row in prev:
        same_run = row.get("run_id") == run_id
        same_digest = row.get("tool_event_digest") == tool_event_digest
        if same_run and not same_digest:
            collision = True
        if same_digest and not same_run:
            collision = True
    entries = [row for row in prev if row.get("run_id") != run_id and row.get("tool_event_digest") != tool_event_digest]
    entries.append(
        {
            "receipt_id": run_id,
            "run_id": run_id,
            "stored_seq": 0,
            "tool_event_digest": tool_event_digest,
            "tool_event_ref": tool_event_ref,
            "action_record_ref": action_record_ref,
        }
    )
    entries.sort(key=lambda r: (str(r.get("run_id", "")), str(r.get("tool_event_digest", ""))))
    for idx, row in enumerate(entries, start=1):
        row["stored_seq"] = idx
    _write_entries(repo_root, entries)
    stored_seq = 0
    for row in entries:
        if row.get("run_id") == run_id and row.get("tool_event_digest") == tool_event_digest:
            stored_seq = int(row.get("stored_seq", 0))
            break
    return {
        "stored_seq": stored_seq,
        "TOOL_EVENT_STORE_COLLISION": "YES" if collision else "NO",
        "store_root": str(tool_event_store_root(repo_root)).replace("\\", "/"),
    }


def get_tool_event_by_digest(repo_root: Path, digest: str) -> dict[str, Any] | None:
    token = str(digest or "").strip()
    if not _DIGEST_RE.fullmatch(token):
        return None
    for row in _load_entries(repo_root):
        if row.get("tool_event_digest") == token:
            return row
    return None


def list_tool_events_recent(repo_root: Path, limit: int) -> list[dict[str, Any]]:
    try:
        n = int(limit)
    except Exception:
        n = 10
    n = max(1, min(n, 100))
    rows = _load_entries(repo_root)
    rows.sort(key=lambda r: int(r.get("stored_seq", 0)))
    return rows[-n:]


def list_tool_events_for_receipt(repo_root: Path, receipt_id: str) -> list[dict[str, Any]]:
    rows = [r for r in _load_entries(repo_root) if r.get("receipt_id") == receipt_id]
    rows.sort(key=lambda r: int(r.get("stored_seq", 0)))
    return rows


def list_all_tool_events(repo_root: Path) -> list[dict[str, Any]]:
    rows = _load_entries(repo_root)
    rows.sort(key=lambda r: int(r.get("stored_seq", 0)))
    return rows


def list_slice(
    repo_root: Path,
    receipt_id: str = "any",
    digest_prefix: str = "",
    limit: int = 25,
) -> list[dict[str, Any]]:
    token_receipt = str(receipt_id or "any").strip() or "any"
    if token_receipt != "any" and not _RUN_ID_RE.fullmatch(token_receipt):
        raise ValueError("FILTER_INVALID")
    token_prefix = str(digest_prefix or "").strip().lower()
    if token_prefix and not _HEX_PREFIX_RE.fullmatch(token_prefix):
        raise ValueError("FILTER_INVALID")
    try:
        n = int(limit)
    except Exception as exc:
        raise ValueError("FILTER_INVALID") from exc
    if n < 1 or n > 100:
        raise ValueError("FILTER_INVALID")

    rows = _load_entries(repo_root)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        run_id = str(row.get("run_id", ""))
        digest = str(row.get("tool_event_digest", ""))
        if token_receipt != "any" and run_id != token_receipt:
            continue
        if token_prefix and not digest.startswith(f"sha256:{token_prefix}"):
            continue
        filtered.append(row)
    filtered.sort(key=lambda r: (int(r.get("stored_seq", 0)), str(r.get("run_id", "")), str(r.get("tool_event_digest", ""))))
    return filtered[:n]


def upsert_tool_event_bundle(
    repo_root: Path,
    bundle_id: str,
    manifest_sha256: str,
    tool_event_digests_count: int,
    bundle_ref: str,
) -> dict[str, Any]:
    prev = _load_bundle_entries(repo_root)
    entries = [r for r in prev if r.get("bundle_id") != bundle_id]
    entries.append(
        {
            "bundle_id": bundle_id,
            "manifest_sha256": manifest_sha256,
            "tool_event_digests_count": int(tool_event_digests_count),
            "bundle_ref": bundle_ref,
            "stored_seq": 0,
        }
    )
    entries.sort(key=lambda r: str(r.get("bundle_id", "")))
    for idx, row in enumerate(entries, start=1):
        row["stored_seq"] = idx
    _write_bundle_entries(repo_root, entries)
    for row in entries:
        if row.get("bundle_id") == bundle_id:
            return _clean_bundle_entry(row)
    return {
        "bundle_id": bundle_id,
        "manifest_sha256": manifest_sha256,
        "tool_event_digests_count": int(tool_event_digests_count),
        "bundle_ref": bundle_ref,
        "stored_seq": 0,
    }


def get_tool_event_bundle(repo_root: Path, bundle_id: str) -> dict[str, Any] | None:
    token = str(bundle_id or "").strip()
    if not _BUNDLE_ID_RE.fullmatch(token):
        return None
    for row in _load_bundle_entries(repo_root):
        if row.get("bundle_id") == token:
            return row
    return None
