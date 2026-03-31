from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_MAX_DOC_BYTES = 32768
_CREATED_FROM_VALUES = {"ingest", "manual", "external"}
_TOOL_ID_RE = re.compile(r"tool_[0-9a-f]{16}$")
_SCHEMA_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY_TOKEN_RE = re.compile(r"^[A-Z0-9_]{2,64}$")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _store_root(repo_root: Path) -> Path:
    return repo_root / "out" / "mcp_tool_catalog"


def _index_path(repo_root: Path) -> Path:
    return _store_root(repo_root) / "index.v1.json"


def _tools_dir(repo_root: Path) -> Path:
    return _store_root(repo_root) / "tools"


def _normalize_declared_capabilities(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("TOOL_DOC_INVALID")
    out = sorted({str(v).strip() for v in value if isinstance(v, str) and str(v).strip()})
    if not out:
        raise ValueError("TOOL_DOC_INVALID")
    return out


def normalize_tool_doc(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("TOOL_DOC_INVALID")
    tool_name = payload.get("tool_name")
    tool_version = payload.get("tool_version")
    schema_json = payload.get("schema_json")
    declared_capabilities = payload.get("declared_capabilities")
    created_from = payload.get("created_from", "external")
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("TOOL_DOC_INVALID")
    if not isinstance(tool_version, str) or not tool_version.strip():
        raise ValueError("TOOL_DOC_INVALID")
    if created_from not in _CREATED_FROM_VALUES:
        raise ValueError("TOOL_DOC_INVALID")
    if not isinstance(schema_json, dict):
        raise ValueError("TOOL_DOC_INVALID")
    schema_raw = _canonical_json(schema_json).encode("utf-8")
    if len(schema_raw) > _MAX_DOC_BYTES:
        raise ValueError("TOOL_DOC_TOO_LARGE")
    schema_sha256 = hashlib.sha256(schema_raw).hexdigest()
    normalized = {
        "tool_name": tool_name.strip(),
        "tool_version": tool_version.strip(),
        "schema_sha256": schema_sha256,
        "schema_json": json.loads(_canonical_json(schema_json)),
        "declared_capabilities": _normalize_declared_capabilities(declared_capabilities),
        "created_from": created_from,
    }
    body_raw = _canonical_json(normalized).encode("utf-8")
    if len(body_raw) > _MAX_DOC_BYTES:
        raise ValueError("TOOL_DOC_TOO_LARGE")
    tool_id = "tool_" + hashlib.sha256(body_raw).hexdigest()[:16]
    normalized["tool_id"] = tool_id
    return normalized


def _validate_loaded_doc(obj: Any, expected_tool_id: str = "") -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("TOOL_DOC_INVALID")
    tool_id = str(obj.get("tool_id", "")).strip()
    if not _TOOL_ID_RE.fullmatch(tool_id):
        raise ValueError("TOOL_DOC_INVALID")
    if expected_tool_id and tool_id != expected_tool_id:
        raise ValueError("TOOL_DOC_INVALID")
    tool_name = obj.get("tool_name")
    tool_version = obj.get("tool_version")
    schema_json = obj.get("schema_json")
    schema_sha256 = str(obj.get("schema_sha256", "")).strip()
    declared_capabilities = obj.get("declared_capabilities")
    created_from = obj.get("created_from")
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("TOOL_DOC_INVALID")
    if not isinstance(tool_version, str) or not tool_version.strip():
        raise ValueError("TOOL_DOC_INVALID")
    if not isinstance(schema_json, dict):
        raise ValueError("TOOL_DOC_INVALID")
    if not _SCHEMA_SHA_RE.fullmatch(schema_sha256):
        raise ValueError("TOOL_DOC_INVALID")
    if created_from not in _CREATED_FROM_VALUES:
        raise ValueError("TOOL_DOC_INVALID")
    declared = _normalize_declared_capabilities(declared_capabilities)
    expected_schema_sha = hashlib.sha256(_canonical_json(schema_json).encode("utf-8")).hexdigest()
    if schema_sha256 != expected_schema_sha:
        raise ValueError("TOOL_DOC_INVALID")
    return {
        "tool_id": tool_id,
        "tool_name": tool_name.strip(),
        "tool_version": tool_version.strip(),
        "schema_sha256": schema_sha256,
        "schema_json": json.loads(_canonical_json(schema_json)),
        "declared_capabilities": declared,
        "created_from": created_from,
    }


def _load_index(repo_root: Path) -> dict[str, Any]:
    p = _index_path(repo_root)
    if not p.is_file():
        return {"index_version": "tool_catalog_index_v1", "next_seq": 1, "events": []}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("TOOL_CATALOG_INDEX_INVALID") from exc
    if not isinstance(obj, dict):
        raise ValueError("TOOL_CATALOG_INDEX_INVALID")
    events = obj.get("events", [])
    if not isinstance(events, list):
        raise ValueError("TOOL_CATALOG_INDEX_INVALID")
    clean_events: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    max_seq = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        seq = event.get("seq")
        tool_id = event.get("tool_id")
        if not isinstance(seq, int) or seq < 1:
            continue
        if not isinstance(tool_id, str) or not tool_id.strip():
            continue
        token = tool_id.strip()
        if not _TOOL_ID_RE.fullmatch(token):
            continue
        key = (seq, token)
        if key in seen:
            continue
        seen.add(key)
        clean_events.append({"seq": seq, "tool_id": token})
        max_seq = max(max_seq, seq)
    clean_events.sort(key=lambda x: (x["seq"], x["tool_id"]))
    return {
        "index_version": "tool_catalog_index_v1",
        "next_seq": max_seq + 1,
        "events": clean_events,
    }


def _write_index(repo_root: Path, obj: dict[str, Any]) -> None:
    p = _index_path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_canonical_json(obj), encoding="utf-8")


def put(repo_root: Path, payload: dict[str, Any]) -> str:
    doc = normalize_tool_doc(payload)
    tools_dir = _tools_dir(repo_root)
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{doc['tool_id']}.json").write_text(_canonical_json(doc), encoding="utf-8")
    index = _load_index(repo_root)
    seq = int(index["next_seq"])
    index["events"].append({"seq": seq, "tool_id": doc["tool_id"]})
    index["events"].sort(key=lambda x: x["seq"])
    index["next_seq"] = seq + 1
    _write_index(repo_root, index)
    return str(doc["tool_id"])


def get(repo_root: Path, tool_id: str) -> dict[str, Any] | None:
    token = str(tool_id or "").strip()
    if not _TOOL_ID_RE.fullmatch(token):
        return None
    p = _tools_dir(repo_root) / f"{token}.json"
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("TOOL_DOC_INVALID") from exc
    return _validate_loaded_doc(obj, expected_tool_id=token)


def list_recent(repo_root: Path, limit: int = 10) -> list[dict[str, Any]]:
    try:
        n = int(limit)
    except Exception:
        n = 10
    n = max(1, min(n, 100))
    index = _load_index(repo_root)
    out: list[dict[str, Any]] = []
    for event in sorted(index["events"], key=lambda x: (int(x["seq"]), str(x["tool_id"])), reverse=True):
        try:
            doc = get(repo_root, str(event["tool_id"]))
        except ValueError:
            # Fail closed for malformed docs by excluding unreadable entries from query output.
            continue
        if doc is None:
            continue
        row = dict(doc)
        row["index_seq"] = int(event["seq"])
        out.append(row)
        if len(out) >= n:
            break
    return out


def list_slice(repo_root: Path, created_from: str = "any", capability: str = "", limit: int = 25) -> list[dict[str, Any]]:
    token_created = str(created_from or "any").strip().lower() or "any"
    if token_created != "any" and token_created not in _CREATED_FROM_VALUES:
        raise ValueError("FILTER_INVALID")

    token_capability = str(capability or "").strip().upper()
    if token_capability and not _CAPABILITY_TOKEN_RE.fullmatch(token_capability):
        raise ValueError("FILTER_INVALID")

    try:
        n = int(limit)
    except Exception as exc:
        raise ValueError("FILTER_INVALID") from exc
    n = max(1, min(n, 500))

    index = _load_index(repo_root)
    out: list[dict[str, Any]] = []
    for event in sorted(index["events"], key=lambda x: (int(x["seq"]), str(x["tool_id"])), reverse=True):
        try:
            doc = get(repo_root, str(event["tool_id"]))
        except ValueError:
            continue
        if doc is None:
            continue
        if token_created != "any" and str(doc.get("created_from", "")).strip() != token_created:
            continue
        capabilities = doc.get("declared_capabilities", [])
        if token_capability and (not isinstance(capabilities, list) or token_capability not in capabilities):
            continue
        row = dict(doc)
        row["index_seq"] = int(event["seq"])
        out.append(row)
        if len(out) >= n:
            break
    return out


def store_root(repo_root: Path) -> Path:
    return _store_root(repo_root)
