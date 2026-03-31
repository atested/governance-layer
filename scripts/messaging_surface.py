#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MESSAGING_MAP_PATH = REPO_ROOT / "capabilities" / "messaging-tool-map.v1.json"
DEFAULT_MESSAGING_PROXY_ROOT = REPO_ROOT / "out" / "messaging_proxy"
PAYLOAD_HANDLE_PREFIX = "msgpayload://repo-rel/"
FORWARD_RECEIPT_FILENAME = "forward_receipt.json"
FORWARD_RECEIPT_VERSION = "msg_forward_receipt.v1"

CONTENT_FIELD_NAMES = frozenset(
    {
        "attachment_bytes",
        "attachment_names",
        "attachments",
        "body",
        "content",
        "html",
        "message_text",
        "preview",
        "quoted_text",
        "rendered_preview",
        "subject",
        "summary",
        "text",
    }
)


def messaging_map_path() -> Path:
    raw = os.environ.get("GOV_MESSAGING_MAP_PATH", "").strip()
    if not raw:
        return DEFAULT_MESSAGING_MAP_PATH
    return Path(raw)


def load_messaging_map() -> tuple[bytes, dict[str, Any], str]:
    path = messaging_map_path()
    raw = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("MESSAGING_MAP_INVALID_TOPLEVEL")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("MESSAGING_MAP_INVALID_ENTRIES")
    return raw, data, digest


def sha256_prefixed_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def find_mapping_entry(mapping_doc: dict[str, Any], surface_binding_id: str) -> dict[str, Any] | None:
    for entry in mapping_doc.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("surface_binding_id", "")) == str(surface_binding_id):
            return entry
    return None


def contains_content_fields(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) in CONTENT_FIELD_NAMES:
                return True
            if contains_content_fields(value):
                return True
        return False
    if isinstance(obj, list):
        return any(contains_content_fields(item) for item in obj)
    return False


def parse_nonnegative_int(raw: Any, default: int = 0) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < 0:
        return default
    return value


def resolve_repo_relative_payload_handle(handle: str, repo_root: Path) -> Path:
    if not isinstance(handle, str) or not handle.startswith(PAYLOAD_HANDLE_PREFIX):
        raise ValueError("MSG_PAYLOAD_HANDLE_INVALID")
    rel = handle[len(PAYLOAD_HANDLE_PREFIX) :]
    if not rel:
        raise ValueError("MSG_PAYLOAD_HANDLE_INVALID")
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ValueError("MSG_PAYLOAD_HANDLE_INVALID")
    resolved = (repo_root / rel_path).resolve(strict=False)
    repo_resolved = repo_root.resolve(strict=False)
    resolved.relative_to(repo_resolved)
    return resolved
