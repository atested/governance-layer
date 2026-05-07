#!/usr/bin/env python3
"""Machine identity helpers for single-machine and future sync records."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from storage_contract import runtime_root
except ImportError:  # pragma: no cover - package import path
    from scripts.storage_contract import runtime_root


MACHINE_IDENTITY_VERSION = 1
MACHINE_REGISTRY_VERSION = 1
DEFAULT_MACHINE_ROLE = "primary"
VALID_MACHINE_ROLES = {"primary", "remote"}
ACTIVE_LICENSE_STATUS = "active"


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(obj: Any) -> str:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def sha256_prefixed_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def machine_dir(repo_root: Path) -> Path:
    return runtime_root(repo_root) / "machines"


def machine_identity_path(repo_root: Path) -> Path:
    return machine_dir(repo_root) / "identity.json"


def machine_registry_path(repo_root: Path) -> Path:
    return machine_dir(repo_root) / "registry.json"


def _normalized_role(role: Optional[str]) -> str:
    candidate = str(role or os.environ.get("GOV_MACHINE_ROLE", "") or DEFAULT_MACHINE_ROLE).strip().lower()
    return candidate if candidate in VALID_MACHINE_ROLES else DEFAULT_MACHINE_ROLE


def _env_identity() -> Optional[dict]:
    machine_id = str(os.environ.get("GOV_MACHINE_ID", "")).strip()
    if not machine_id:
        return None
    role = _normalized_role(os.environ.get("GOV_MACHINE_ROLE"))
    return {
        "identity_version": MACHINE_IDENTITY_VERSION,
        "installation_id": str(os.environ.get("GOV_INSTALLATION_ID", "")).strip() or machine_id,
        "machine_id": machine_id,
        "machine_role": role,
        "display_name": str(os.environ.get("GOV_MACHINE_DISPLAY_NAME", "")).strip() or platform.node(),
        "created_utc": str(os.environ.get("GOV_MACHINE_CREATED_UTC", "")).strip() or now_utc_z(),
        "signing_key_id": str(os.environ.get("GOV_MACHINE_SIGNING_KEY_ID", "")).strip() or None,
    }


def load_machine_identity(repo_root: Path) -> Optional[dict]:
    env_identity = _env_identity()
    if env_identity is not None:
        return env_identity
    path = machine_identity_path(repo_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("machine_id"), str) or not data.get("machine_id"):
        return None
    data["machine_role"] = _normalized_role(data.get("machine_role"))
    return data


def save_machine_identity(repo_root: Path, identity: dict) -> dict:
    path = machine_identity_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical_json(identity) + "\n", encoding="utf-8")
    tmp.replace(path)
    return identity


def ensure_machine_identity(
    repo_root: Path,
    *,
    role: Optional[str] = None,
    display_name: Optional[str] = None,
    signing_key_id: Optional[str] = None,
) -> dict:
    """Load or create this machine's persistent local identity."""
    existing = load_machine_identity(repo_root)
    if existing is not None:
        changed = False
        if signing_key_id and not existing.get("signing_key_id"):
            existing["signing_key_id"] = signing_key_id
            changed = True
        if changed and _env_identity() is None:
            save_machine_identity(repo_root, existing)
        return existing

    created = now_utc_z()
    identity = {
        "identity_version": MACHINE_IDENTITY_VERSION,
        "installation_id": str(uuid.uuid4()),
        "machine_id": str(uuid.uuid4()),
        "machine_role": _normalized_role(role),
        "display_name": str(display_name or platform.node() or "primary"),
        "created_utc": created,
        "signing_key_id": signing_key_id,
    }
    return save_machine_identity(repo_root, identity)


def machine_identity_fields(repo_root: Path, *, event_timestamp_utc: Optional[str] = None) -> dict:
    identity = ensure_machine_identity(repo_root)
    return {
        "machine_id": identity["machine_id"],
        "machine_role": identity["machine_role"],
        "event_timestamp_utc": event_timestamp_utc or now_utc_z(),
    }


def add_machine_identity_fields(record: dict, repo_root: Path) -> dict:
    """Ensure a governance record carries the required machine fields."""
    event_ts = record.get("event_timestamp_utc") or record.get("timestamp_utc") or now_utc_z()
    fields = machine_identity_fields(repo_root, event_timestamp_utc=str(event_ts))
    record.setdefault("machine_id", fields["machine_id"])
    record.setdefault("machine_role", fields["machine_role"])
    record.setdefault("event_timestamp_utc", fields["event_timestamp_utc"])
    return record


def _registry_hash(registry: dict) -> str:
    body = dict(registry)
    body["registry_hash"] = None
    return sha256_prefixed_text(canonical_json(body))


def save_machine_registry(repo_root: Path, registry: dict) -> dict:
    registry["registry_hash"] = _registry_hash(registry)
    path = machine_registry_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical_json(registry) + "\n", encoding="utf-8")
    tmp.replace(path)
    return registry


def load_machine_registry(repo_root: Path) -> Optional[dict]:
    path = machine_registry_path(repo_root)
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(registry, dict):
        return None
    expected = registry.get("registry_hash")
    if isinstance(expected, str) and expected != _registry_hash(registry):
        return None
    return registry


def ensure_primary_machine_registry(
    repo_root: Path,
    *,
    identity: Optional[dict] = None,
    public_key_fingerprint: Optional[str] = None,
) -> dict:
    """Create the v1 local registry for the primary if it does not exist."""
    identity = identity or ensure_machine_identity(repo_root, role=DEFAULT_MACHINE_ROLE)
    registry = load_machine_registry(repo_root)
    if registry is None:
        registry = {
            "registry_version": MACHINE_REGISTRY_VERSION,
            "installation_id": identity.get("installation_id"),
            "machines": [],
            "registry_hash": None,
        }

    machine_id = identity["machine_id"]
    machines = registry.setdefault("machines", [])
    existing = next((m for m in machines if m.get("machine_id") == machine_id), None)
    key_id = public_key_fingerprint or identity.get("signing_key_id")
    if existing is None:
        machines.append({
            "machine_id": machine_id,
            "role": identity.get("machine_role", DEFAULT_MACHINE_ROLE),
            "display_name": identity.get("display_name", platform.node()),
            "public_key_fingerprint": key_id,
            "license_status": ACTIVE_LICENSE_STATUS,
            "sync_authorized": True,
            "first_seen_utc": identity.get("created_utc") or now_utc_z(),
            "last_sync_utc": None,
            "keys": [{
                "public_key_fingerprint": key_id,
                "public_key_pem": "",
                "valid_from_utc": identity.get("created_utc") or now_utc_z(),
                "valid_until_utc": None,
                "revoked_utc": None,
            }],
        })
    elif key_id:
        existing["public_key_fingerprint"] = existing.get("public_key_fingerprint") or key_id
        keys = existing.setdefault("keys", [])
        if not any(k.get("public_key_fingerprint") == key_id for k in keys):
            keys.append({
                "public_key_fingerprint": key_id,
                "public_key_pem": "",
                "valid_from_utc": now_utc_z(),
                "valid_until_utc": None,
                "revoked_utc": None,
            })
    return save_machine_registry(repo_root, registry)


def authorized_machine_lookup(
    repo_root: Path,
    machine_id: str,
    public_key_fingerprint: str,
) -> Optional[dict]:
    """Return the registry row if a machine is authorized for sync."""
    registry = load_machine_registry(repo_root)
    if not registry:
        return None
    for machine in registry.get("machines", []):
        if machine.get("machine_id") != machine_id:
            continue
        if not machine.get("sync_authorized"):
            return None
        if machine.get("license_status") != ACTIVE_LICENSE_STATUS:
            return None
        for key in machine.get("keys", []):
            if key.get("public_key_fingerprint") != public_key_fingerprint:
                continue
            if key.get("revoked_utc") or key.get("valid_until_utc"):
                return None
            return machine
    return None
