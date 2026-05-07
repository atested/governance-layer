#!/usr/bin/env python3
"""Shared helpers for multi-machine telemetry, relay, versions, and restore."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

try:
    from machine_identity import load_machine_identity, load_machine_registry, save_machine_registry, now_utc_z
    from storage_contract import runtime_root
    from sync_protocol import SYNC_PROTOCOL_VERSION, canonical_json, sha256_json
except ImportError:  # pragma: no cover - package import path
    from scripts.machine_identity import load_machine_identity, load_machine_registry, save_machine_registry, now_utc_z
    from scripts.storage_contract import runtime_root
    from scripts.sync_protocol import SYNC_PROTOCOL_VERSION, canonical_json, sha256_json


REMOTE_TELEMETRY_DIR = "sync/remote_telemetry"
RELAYED_COMMUNICATIONS_PATH = "sync/communications.jsonl"
DEFAULT_MIN_REMOTE_VERSION = "0.0.0"


def product_version(repo_root: Path) -> str:
    version_path = Path(repo_root) / "VERSION"
    try:
        value = version_path.read_text(encoding="utf-8").strip()
    except OSError:
        value = ""
    return value or "0.0.0"


def minimum_remote_version() -> str:
    return str(os.environ.get("ATESTED_MIN_REMOTE_VERSION", DEFAULT_MIN_REMOTE_VERSION)).strip() or DEFAULT_MIN_REMOTE_VERSION


def parse_version(value: Any) -> tuple[int, ...]:
    parts: list[int] = []
    for raw in str(value or "0.0.0").split("."):
        digits = ""
        for char in raw:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def version_is_below(value: str, minimum: str) -> bool:
    return parse_version(value) < parse_version(minimum)


def validate_sync_versions(payload: dict, repo_root: Path) -> tuple[bool, dict]:
    protocol = str(payload.get("protocol_version") or "").strip()
    remote_version = str(payload.get("product_version") or "").strip() or "0.0.0"
    if protocol != SYNC_PROTOCOL_VERSION:
        return False, {
            "accepted": False,
            "error": "UPDATE_REQUIRED_SYNC_PROTOCOL_INCOMPATIBLE",
            "message": "Remote sync protocol is incompatible. Update the remote before syncing.",
            "supported_protocol_versions": [SYNC_PROTOCOL_VERSION],
            "remote_protocol_version": protocol,
        }
    minimum = minimum_remote_version()
    if version_is_below(remote_version, minimum):
        return False, {
            "accepted": False,
            "error": "UPDATE_REQUIRED_REMOTE_VERSION_TOO_OLD",
            "message": "Remote product version is below the minimum supported version. Update the remote before syncing.",
            "minimum_supported_version": minimum,
            "remote_product_version": remote_version,
            "primary_product_version": product_version(repo_root),
        }
    return True, {}


def update_machine_version_report(
    repo_root: Path,
    machine_id: str,
    *,
    product_version_value: str,
    protocol_version: str,
) -> Optional[dict]:
    registry = load_machine_registry(repo_root)
    if not registry:
        return None
    minimum = minimum_remote_version()
    changed = False
    for machine in registry.get("machines", []):
        if machine.get("machine_id") != machine_id:
            continue
        version_status = "ok"
        if protocol_version != SYNC_PROTOCOL_VERSION:
            version_status = "protocol_incompatible"
        elif version_is_below(product_version_value, minimum):
            version_status = "stale_update_required"
        elif version_is_below(product_version_value, product_version(repo_root)):
            version_status = "stale"
        machine["product_version"] = product_version_value
        machine["sync_protocol_version"] = protocol_version
        machine["version_status"] = version_status
        machine["minimum_supported_version"] = minimum
        machine["last_version_report_utc"] = now_utc_z()
        changed = True
        break
    return save_machine_registry(repo_root, registry) if changed else registry


def load_local_telemetry_summary(repo_root: Path) -> Optional[dict]:
    path = runtime_root(repo_root) / "LOGS" / "telemetry" / "summary.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def remote_telemetry_payload(repo_root: Path) -> Optional[dict]:
    summary = load_local_telemetry_summary(repo_root)
    if not summary:
        return None
    identity = load_machine_identity(repo_root) or {}
    return {
        "machine_id": identity.get("machine_id"),
        "machine_role": identity.get("machine_role"),
        "summary": summary,
        "summary_hash": sha256_json(summary),
    }


def store_remote_telemetry_summary(repo_root: Path, source_machine_id: str, telemetry_payload: Any) -> Optional[dict]:
    if not isinstance(telemetry_payload, dict):
        return None
    summary = telemetry_payload.get("summary")
    if not isinstance(summary, dict):
        return None
    reported_hash = telemetry_payload.get("summary_hash")
    actual_hash = sha256_json(summary)
    if isinstance(reported_hash, str) and reported_hash and reported_hash != actual_hash:
        raise ValueError("REMOTE_TELEMETRY_HASH_MISMATCH")
    record = {
        "machine_id": source_machine_id,
        "machine_role": telemetry_payload.get("machine_role") or "remote",
        "received_at_utc": now_utc_z(),
        "summary_hash": actual_hash,
        "summary": summary,
    }
    path = runtime_root(repo_root) / REMOTE_TELEMETRY_DIR / f"{_safe_machine_id(source_machine_id)}.json"
    _write_json(path, record)
    return record


def load_remote_telemetry_summaries(repo_root: Path) -> list[dict]:
    root = runtime_root(repo_root) / REMOTE_TELEMETRY_DIR
    items: list[dict] = []
    if not root.exists():
        return items
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            items.append(data)
    return items


def apply_machine_coverage_to_telemetry_artifact(repo_root: Path, artifact: dict) -> dict:
    enriched = dict(artifact)
    identity = load_machine_identity(repo_root) or {}
    local_summary = load_local_telemetry_summary(repo_root)
    machines: list[dict] = []
    if local_summary is not None:
        machines.append({
            "machine_id": identity.get("machine_id"),
            "machine_role": identity.get("machine_role") or "primary",
            "summary_hash": sha256_json(local_summary),
            "source": "primary_local",
        })
    for remote in load_remote_telemetry_summaries(repo_root):
        machines.append({
            "machine_id": remote.get("machine_id"),
            "machine_role": remote.get("machine_role") or "remote",
            "summary_hash": remote.get("summary_hash"),
            "received_at_utc": remote.get("received_at_utc"),
            "source": "remote_sync",
        })
    enriched["machine_coverage"] = [m for m in machines if m.get("machine_id")]
    enriched["machine_coverage_count"] = len(enriched["machine_coverage"])
    enriched["remote_telemetry_summary_count"] = len(load_remote_telemetry_summaries(repo_root))
    enriched["artifact_hash"] = "sha256:" + hashlib.sha256(
        canonical_json({**enriched, "artifact_hash": None}).encode("utf-8")
    ).hexdigest()
    return enriched


def telemetry_submission_event_payload(destination: str, artifact: dict) -> dict:
    payload_bytes = canonical_json(artifact).encode("utf-8")
    return {
        "destination": destination,
        "payload_hash": artifact.get("artifact_hash") or "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
        "payload_size": len(payload_bytes),
        "machine_coverage": artifact.get("machine_coverage", []),
        "machine_coverage_count": int(artifact.get("machine_coverage_count") or 0),
    }


def stable_message_id(message: dict) -> str:
    for key in ("message_id", "notification_id", "request_id", "id"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return sha256_json(message)


def normalize_communications(messages: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        normalized = dict(message)
        message_id = stable_message_id(normalized)
        if message_id in seen:
            continue
        seen.add(message_id)
        normalized["message_id"] = message_id
        normalized.setdefault("relayed_message_id", message_id)
        result.append(normalized)
    return result


def store_relayed_communications(repo_root: Path, communications: list[dict]) -> list[dict]:
    path = runtime_root(repo_root) / RELAYED_COMMUNICATIONS_PATH
    existing = _read_jsonl(path)
    merged = normalize_communications(existing + normalize_communications(communications))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(canonical_json(item) + "\n" for item in merged),
        encoding="utf-8",
    )
    return merged


def validate_primary_restore_runtime(repo_root: Path, runtime: Optional[Path] = None) -> dict:
    runtime = Path(runtime) if runtime is not None else runtime_root(repo_root)
    required = {
        "decision_chain": runtime / "LOGS" / "decision-chain.jsonl",
        "machine_registry": runtime / "machines" / "registry.json",
        "signing_key": runtime / ".atested-signing-key.pem",
    }
    optional = {
        "imports": runtime / "imports",
        "approvals": runtime / "approvals",
        "communications": runtime / "LOGS" / "update_notifications.jsonl",
        "telemetry": runtime / "LOGS" / "telemetry",
        "archives": runtime / "LOGS" / "archives",
        "policy_rules": Path(repo_root) / "capabilities" / "policy-rules.json",
    }
    checks: list[dict] = []
    ok = True
    for name, path in required.items():
        exists = path.exists()
        checks.append({"name": name, "path": str(path), "required": True, "present": exists})
        ok = ok and exists
    for name, path in optional.items():
        checks.append({"name": name, "path": str(path), "required": False, "present": path.exists()})

    registry_valid = False
    try:
        registry = json.loads(required["machine_registry"].read_text(encoding="utf-8"))
        expected = registry.get("registry_hash")
        body = dict(registry)
        body["registry_hash"] = None
        registry_valid = isinstance(expected, str) and expected == "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    except (OSError, json.JSONDecodeError):
        registry_valid = False
    checks.append({"name": "machine_registry_hash", "required": True, "present": registry_valid})
    ok = ok and registry_valid

    chain_status = "missing"
    if required["decision_chain"].exists():
        try:
            from readout import check_chain_integrity
        except ImportError:  # pragma: no cover
            from scripts.readout import check_chain_integrity
        chain_result = check_chain_integrity(required["decision_chain"])
        chain_status = str(chain_result.get("status") or "unknown")
        ok = ok and chain_status == "ok"
    checks.append({"name": "chain_integrity", "required": True, "present": chain_status == "ok", "status": chain_status})

    return {
        "restore_runtime_valid": bool(ok),
        "runtime": str(runtime),
        "checks": checks,
        "required_contents": [str(path) for path in required.values()],
        "message": "restore runtime is valid" if ok else "restore runtime is incomplete or failed verification",
    }


def _safe_machine_id(machine_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(machine_id))[:160] or "unknown"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return items
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            items.append(record)
    return items
