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
    from canonical_form import canonical_json as _canonical_form_json
    from storage_contract import runtime_root
except ImportError:  # pragma: no cover - package import path
    from scripts.canonical_form import canonical_json as _canonical_form_json
    from scripts.storage_contract import runtime_root


MACHINE_IDENTITY_VERSION = 1
MACHINE_REGISTRY_VERSION = 1
DEFAULT_MACHINE_ROLE = "primary"
VALID_MACHINE_ROLES = {"primary", "remote"}
ACTIVE_LICENSE_STATUS = "active"
REMOVED_LICENSE_STATUS = "removed"


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(obj: Any) -> str:
    return _canonical_form_json(obj)


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


def add_record_freshness_fields(record: dict, repo_root: Path) -> dict:
    """Ensure a governance record carries freshness hashes.

    Decision records normally set these from the active approval store and
    loaded policy. Non-action events do not have decision context, so this
    helper adds the current local policy hash and an empty approval-store hash
    only when the caller did not already provide values.
    """
    if not record.get("approval_store_hash"):
        try:
            from approval_store import approval_store_hash
            record["approval_store_hash"] = approval_store_hash(None)
        except Exception:
            record["approval_store_hash"] = "sha256:" + ("0" * 64)
    if not record.get("policy_rules_hash"):
        try:
            from policy_eval_v2 import compute_policy_rules_hash, load_policy_rules
            policy_path = os.environ.get("GOV_POLICY_RULES_PATH", "").strip()
            policy = load_policy_rules(Path(policy_path) if policy_path else None)
            record["policy_rules_hash"] = compute_policy_rules_hash(policy)
        except Exception:
            record["policy_rules_hash"] = "sha256:" + ("0" * 64)
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
    public_key_pem: Optional[str] = None,
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
            "operator_confirmed_utc": identity.get("created_utc") or now_utc_z(),
            "operator_confirmation_event_id": "primary-bootstrap",
            "first_seen_utc": identity.get("created_utc") or now_utc_z(),
            "last_sync_utc": None,
            "keys": [{
                "public_key_fingerprint": key_id,
                "public_key_pem": public_key_pem or "",
                "valid_from_utc": identity.get("created_utc") or now_utc_z(),
                "valid_until_utc": None,
                "revoked_utc": None,
            }],
        })
    elif key_id:
        existing.setdefault("operator_confirmed_utc", identity.get("created_utc") or now_utc_z())
        existing.setdefault("operator_confirmation_event_id", "primary-bootstrap")
        existing["public_key_fingerprint"] = existing.get("public_key_fingerprint") or key_id
        keys = existing.setdefault("keys", [])
        if not any(k.get("public_key_fingerprint") == key_id for k in keys):
            keys.append({
                "public_key_fingerprint": key_id,
                "public_key_pem": public_key_pem or "",
                "valid_from_utc": now_utc_z(),
                "valid_until_utc": None,
                "revoked_utc": None,
            })
        elif public_key_pem:
            for key in keys:
                if key.get("public_key_fingerprint") == key_id and not key.get("public_key_pem"):
                    key["public_key_pem"] = public_key_pem
    return save_machine_registry(repo_root, registry)


def _parse_utc(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def key_is_valid_at(key: dict, at_utc: Optional[str] = None) -> bool:
    at = _parse_utc(at_utc) or datetime.now(timezone.utc)
    valid_from = _parse_utc(key.get("valid_from_utc"))
    valid_until = _parse_utc(key.get("valid_until_utc"))
    revoked = _parse_utc(key.get("revoked_utc"))
    if valid_from is not None and at < valid_from:
        return False
    if valid_until is not None and at >= valid_until:
        return False
    if revoked is not None and at >= revoked:
        return False
    return True


def authorized_machine_lookup(
    repo_root: Path,
    machine_id: str,
    public_key_fingerprint: str,
    *,
    at_utc: Optional[str] = None,
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
        if not machine.get("operator_confirmed_utc") or not machine.get("operator_confirmation_event_id"):
            return None
        if not _chain_authorizes_machine_key(repo_root, machine, public_key_fingerprint):
            return None
        for key in machine.get("keys", []):
            if key.get("public_key_fingerprint") != public_key_fingerprint:
                continue
            if not key_is_valid_at(key, at_utc):
                return None
            return machine
    return None


def _chain_authorizes_machine_key(repo_root: Path, machine: dict, public_key_fingerprint: str) -> bool:
    if machine.get("operator_confirmation_event_id") == "primary-bootstrap" and machine.get("role") == "primary":
        return True
    machine_id = machine.get("machine_id")
    chain = runtime_root(repo_root) / "LOGS" / "decision-chain.jsonl"
    try:
        lines = chain.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    authorized_keys: set[str] = set()
    sync_authorized = False
    license_active = False
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("subject_machine_id") != machine_id:
            continue
        event_type = event.get("event_type")
        if event_type == "machine_added":
            key_id = event.get("public_key_fingerprint")
            if isinstance(key_id, str) and key_id:
                authorized_keys.add(key_id)
            sync_authorized = bool(event.get("sync_authorized"))
            license_active = event.get("license_status") == ACTIVE_LICENSE_STATUS
        elif event_type == "machine_key_rotated":
            old_key = event.get("old_public_key_fingerprint")
            new_key = event.get("new_public_key_fingerprint")
            if isinstance(old_key, str):
                authorized_keys.discard(old_key)
            if isinstance(new_key, str) and new_key:
                authorized_keys.add(new_key)
        elif event_type == "machine_license_status_changed":
            sync_authorized = bool(event.get("sync_authorized"))
            license_active = event.get("to_license_status") == ACTIVE_LICENSE_STATUS
        elif event_type == "machine_removed":
            sync_authorized = False
            license_active = False
    return sync_authorized and license_active and public_key_fingerprint in authorized_keys


def _machine_row(registry: dict, machine_id: str) -> Optional[dict]:
    for machine in registry.get("machines", []):
        if machine.get("machine_id") == machine_id:
            return machine
    return None


def _registry_event(
    repo_root: Path,
    event_type: str,
    payload: dict,
    *,
    registry_hash_before: Optional[str],
    registry_hash_after: Optional[str],
    append_event=None,
) -> dict:
    try:
        from event_model import build_non_action_event
    except ImportError:  # pragma: no cover - package import path
        from scripts.event_model import build_non_action_event

    event = build_non_action_event(
        event_type,
        {
            **payload,
            "registry_hash_before": registry_hash_before,
            "registry_hash_after": registry_hash_after,
        },
    )
    if append_event is not None:
        return append_event(event)
    return event


def add_machine_to_registry(
    repo_root: Path,
    *,
    machine_id: str,
    role: str,
    display_name: str,
    public_key_fingerprint: str,
    public_key_pem: str,
    operator_confirmation_event_id: str,
    license_status: str = ACTIVE_LICENSE_STATUS,
    sync_authorized: bool = True,
    append_event=None,
) -> tuple[dict, dict]:
    registry = load_machine_registry(repo_root)
    if registry is None:
        identity = ensure_machine_identity(repo_root, role=DEFAULT_MACHINE_ROLE)
        registry = {
            "registry_version": MACHINE_REGISTRY_VERSION,
            "installation_id": identity.get("installation_id"),
            "machines": [],
            "registry_hash": None,
        }
    if _machine_row(registry, machine_id) is not None:
        raise ValueError(f"machine already registered: {machine_id}")
    before = registry.get("registry_hash")
    ts = now_utc_z()
    registry.setdefault("machines", []).append({
        "machine_id": machine_id,
        "role": _normalized_role(role),
        "display_name": display_name,
        "public_key_fingerprint": public_key_fingerprint,
        "license_status": license_status,
        "sync_authorized": bool(sync_authorized),
        "operator_confirmed_utc": ts,
        "operator_confirmation_event_id": operator_confirmation_event_id,
        "first_seen_utc": ts,
        "last_sync_utc": None,
        "keys": [{
            "public_key_fingerprint": public_key_fingerprint,
            "public_key_pem": public_key_pem,
            "valid_from_utc": ts,
            "valid_until_utc": None,
            "revoked_utc": None,
        }],
    })
    saved = save_machine_registry(repo_root, registry)
    event = _registry_event(
        repo_root,
        "machine_added",
        {
            "subject_machine_id": machine_id,
            "subject_machine_role": _normalized_role(role),
            "public_key_fingerprint": public_key_fingerprint,
            "operator_confirmation_event_id": operator_confirmation_event_id,
            "license_status": license_status,
            "sync_authorized": bool(sync_authorized),
        },
        registry_hash_before=before,
        registry_hash_after=saved.get("registry_hash"),
        append_event=append_event,
    )
    return saved, event


def remove_machine_from_registry(
    repo_root: Path,
    machine_id: str,
    *,
    reason: str = "",
    append_event=None,
) -> tuple[dict, dict]:
    registry = load_machine_registry(repo_root)
    if registry is None:
        raise ValueError("registry missing")
    machine = _machine_row(registry, machine_id)
    if machine is None:
        raise ValueError(f"machine not registered: {machine_id}")
    before = registry.get("registry_hash")
    machine["license_status"] = REMOVED_LICENSE_STATUS
    machine["sync_authorized"] = False
    machine["removed_utc"] = now_utc_z()
    saved = save_machine_registry(repo_root, registry)
    event = _registry_event(
        repo_root,
        "machine_removed",
        {
            "subject_machine_id": machine_id,
            "reason": reason,
            "license_status": REMOVED_LICENSE_STATUS,
            "sync_authorized": False,
        },
        registry_hash_before=before,
        registry_hash_after=saved.get("registry_hash"),
        append_event=append_event,
    )
    return saved, event


def change_machine_license_status(
    repo_root: Path,
    machine_id: str,
    license_status: str,
    *,
    sync_authorized: Optional[bool] = None,
    append_event=None,
) -> tuple[dict, dict]:
    registry = load_machine_registry(repo_root)
    if registry is None:
        raise ValueError("registry missing")
    machine = _machine_row(registry, machine_id)
    if machine is None:
        raise ValueError(f"machine not registered: {machine_id}")
    before = registry.get("registry_hash")
    old_status = machine.get("license_status")
    machine["license_status"] = license_status
    if sync_authorized is not None:
        machine["sync_authorized"] = bool(sync_authorized)
    saved = save_machine_registry(repo_root, registry)
    event = _registry_event(
        repo_root,
        "machine_license_status_changed",
        {
            "subject_machine_id": machine_id,
            "from_license_status": old_status,
            "to_license_status": license_status,
            "sync_authorized": machine.get("sync_authorized"),
        },
        registry_hash_before=before,
        registry_hash_after=saved.get("registry_hash"),
        append_event=append_event,
    )
    return saved, event


def change_machine_role(
    repo_root: Path,
    machine_id: str,
    role: str,
    *,
    append_event=None,
) -> tuple[dict, dict]:
    registry = load_machine_registry(repo_root)
    if registry is None:
        raise ValueError("registry missing")
    machine = _machine_row(registry, machine_id)
    if machine is None:
        raise ValueError(f"machine not registered: {machine_id}")
    before = registry.get("registry_hash")
    old_role = machine.get("role")
    new_role = _normalized_role(role)
    machine["role"] = new_role
    saved = save_machine_registry(repo_root, registry)
    event = _registry_event(
        repo_root,
        "machine_role_changed",
        {
            "subject_machine_id": machine_id,
            "from_role": old_role,
            "to_role": new_role,
        },
        registry_hash_before=before,
        registry_hash_after=saved.get("registry_hash"),
        append_event=append_event,
    )
    return saved, event


def rotate_machine_key(
    repo_root: Path,
    machine_id: str,
    *,
    new_public_key_fingerprint: str,
    new_public_key_pem: str,
    append_event=None,
) -> tuple[dict, dict]:
    registry = load_machine_registry(repo_root)
    if registry is None:
        raise ValueError("registry missing")
    machine = _machine_row(registry, machine_id)
    if machine is None:
        raise ValueError(f"machine not registered: {machine_id}")
    before = registry.get("registry_hash")
    ts = now_utc_z()
    old_key = machine.get("public_key_fingerprint")
    for key in machine.setdefault("keys", []):
        if key.get("public_key_fingerprint") == old_key and not key.get("valid_until_utc"):
            key["valid_until_utc"] = ts
    machine["public_key_fingerprint"] = new_public_key_fingerprint
    machine["keys"].append({
        "public_key_fingerprint": new_public_key_fingerprint,
        "public_key_pem": new_public_key_pem,
        "valid_from_utc": ts,
        "valid_until_utc": None,
        "revoked_utc": None,
    })
    saved = save_machine_registry(repo_root, registry)
    event = _registry_event(
        repo_root,
        "machine_key_rotated",
        {
            "subject_machine_id": machine_id,
            "old_public_key_fingerprint": old_key,
            "new_public_key_fingerprint": new_public_key_fingerprint,
        },
        registry_hash_before=before,
        registry_hash_after=saved.get("registry_hash"),
        append_event=append_event,
    )
    return saved, event
