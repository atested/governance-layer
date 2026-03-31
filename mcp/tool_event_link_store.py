from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from storage_contract import tool_event_link_index_path
from tool_event_store import get_tool_event_by_digest, list_tool_events_for_receipt

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}$")
_RECEIPT_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}$")
_INDEX_VERSION = "v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _index_path(repo_root: Path) -> Path:
    return tool_event_link_index_path(repo_root)


def _empty_index() -> dict[str, list[dict[str, Any]]]:
    return {"receipt_to_tool_events": [], "tool_event_to_receipts": []}


def _clean_digests(values: list[Any]) -> list[str]:
    out: list[str] = []
    for item in values:
        token = str(item or "").strip()
        if _DIGEST_RE.fullmatch(token):
            out.append(token)
    return sorted(set(out))


def _clean_receipt_ids(values: list[Any]) -> list[str]:
    out: list[str] = []
    for item in values:
        token = str(item or "").strip()
        if _RECEIPT_ID_RE.fullmatch(token):
            out.append(token)
    return sorted(set(out))


def _normalize_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    receipt_rows = payload.get("receipt_to_tool_events", [])
    reverse_rows = payload.get("tool_event_to_receipts", [])
    if not isinstance(receipt_rows, list) or not isinstance(reverse_rows, list):
        return _empty_index()

    receipt_map: dict[str, list[str]] = {}
    for row in receipt_rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("receipt_id", "")).strip()
        if not _RECEIPT_ID_RE.fullmatch(rid):
            continue
        vals = row.get("tool_event_digests", [])
        if not isinstance(vals, list):
            continue
        digests = _clean_digests(vals)
        if not digests:
            continue
        receipt_map.setdefault(rid, [])
        receipt_map[rid].extend(digests)

    for rid in list(receipt_map):
        receipt_map[rid] = sorted(set(receipt_map[rid]))

    tool_map: dict[str, list[str]] = {}
    for rid in sorted(receipt_map):
        for digest in receipt_map[rid]:
            tool_map.setdefault(digest, [])
            tool_map[digest].append(rid)
    for digest in list(tool_map):
        tool_map[digest] = sorted(set(tool_map[digest]))

    return {
        "receipt_to_tool_events": [
            {"receipt_id": rid, "tool_event_digests": receipt_map[rid]}
            for rid in sorted(receipt_map)
        ],
        "tool_event_to_receipts": [
            {"tool_event_digest": digest, "receipt_ids": tool_map[digest]}
            for digest in sorted(tool_map)
        ],
    }


def _load(repo_root: Path) -> dict[str, list[dict[str, Any]]]:
    path = _index_path(repo_root)
    if not path.is_file():
        return _empty_index()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_index()
    if not isinstance(payload, dict):
        return _empty_index()
    version = payload.get("tool_event_link_index_version")
    if version is not None and str(version) != _INDEX_VERSION:
        return _empty_index()
    return _normalize_payload(payload)


def _write(repo_root: Path, payload: dict[str, Any]) -> None:
    path = _index_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_payload(payload if isinstance(payload, dict) else {})
    out = {
        "tool_event_link_index_version": _INDEX_VERSION,
        "receipt_to_tool_events": normalized["receipt_to_tool_events"],
        "tool_event_to_receipts": normalized["tool_event_to_receipts"],
    }
    path.write_text(_canonical_json(out) + "\n", encoding="utf-8")


def upsert_receipt_tool_event_links(repo_root: Path, receipt_id: str, tool_event_digests: list[Any]) -> None:
    rid = str(receipt_id or "").strip()
    if not _RECEIPT_ID_RE.fullmatch(rid):
        return
    digests = _clean_digests(tool_event_digests)
    payload = _load(repo_root)

    receipt_map: dict[str, list[str]] = {}
    for row in payload["receipt_to_tool_events"]:
        if not isinstance(row, dict):
            continue
        key = str(row.get("receipt_id", "")).strip()
        if not _RECEIPT_ID_RE.fullmatch(key):
            continue
        vals = row.get("tool_event_digests", [])
        if isinstance(vals, list):
            cleaned = _clean_digests(vals)
            if cleaned:
                receipt_map[key] = cleaned
    if digests:
        receipt_map[rid] = digests
    elif rid in receipt_map:
        del receipt_map[rid]

    tool_map: dict[str, list[str]] = {}
    for receipt_key in sorted(receipt_map):
        for digest in receipt_map[receipt_key]:
            tool_map.setdefault(digest, [])
            tool_map[digest].append(receipt_key)
    for digest in list(tool_map):
        tool_map[digest] = sorted(set(tool_map[digest]))

    payload_out = {
        "receipt_to_tool_events": [
            {"receipt_id": key, "tool_event_digests": receipt_map[key]}
            for key in sorted(receipt_map)
        ],
        "tool_event_to_receipts": [
            {"tool_event_digest": key, "receipt_ids": tool_map[key]}
            for key in sorted(tool_map)
        ],
    }
    _write(repo_root, payload_out)


def get_tool_events_for_receipt(repo_root: Path, receipt_id: str) -> list[str]:
    rid = str(receipt_id or "").strip()
    if not _RECEIPT_ID_RE.fullmatch(rid):
        return []
    runtime_digests = [
        str(row.get("tool_event_digest", "")).strip()
        for row in list_tool_events_for_receipt(repo_root, rid)
        if _DIGEST_RE.fullmatch(str(row.get("tool_event_digest", "")).strip())
    ]
    payload = _load(repo_root)
    for row in payload["receipt_to_tool_events"]:
        if not isinstance(row, dict):
            continue
        if str(row.get("receipt_id", "")).strip() == rid:
            vals = row.get("tool_event_digests", [])
            if isinstance(vals, list):
                return _clean_digests(list(vals) + runtime_digests)
            return _clean_digests(runtime_digests)
    return _clean_digests(runtime_digests)


def get_receipts_for_tool_event(repo_root: Path, tool_event_digest: str) -> list[str]:
    digest = str(tool_event_digest or "").strip()
    if not _DIGEST_RE.fullmatch(digest):
        return []
    runtime_receipts: list[str] = []
    runtime_row = get_tool_event_by_digest(repo_root, digest)
    if isinstance(runtime_row, dict):
        runtime_receipt = str(runtime_row.get("receipt_id", "")).strip()
        if _RECEIPT_ID_RE.fullmatch(runtime_receipt):
            runtime_receipts.append(runtime_receipt)
    payload = _load(repo_root)
    for row in payload["tool_event_to_receipts"]:
        if not isinstance(row, dict):
            continue
        if str(row.get("tool_event_digest", "")).strip() == digest:
            vals = row.get("receipt_ids", [])
            if isinstance(vals, list):
                return _clean_receipt_ids(list(vals) + runtime_receipts)
            return _clean_receipt_ids(runtime_receipts)
    return _clean_receipt_ids(runtime_receipts)
