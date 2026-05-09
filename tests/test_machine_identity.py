"""Tests for local machine identity and registry bootstrap."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from machine_identity import (  # noqa: E402
    add_machine_to_registry,
    add_machine_identity_fields,
    authorized_machine_lookup,
    change_machine_license_status,
    change_machine_role,
    ensure_machine_identity,
    ensure_primary_machine_registry,
    load_machine_identity,
    load_machine_registry,
    machine_identity_path,
    machine_registry_path,
    remove_machine_from_registry,
    rotate_machine_key,
)


def _append_event_to_chain(tmp_path, event):
    chain = tmp_path / "runtime" / "LOGS" / "decision-chain.jsonl"
    chain.parent.mkdir(parents=True, exist_ok=True)
    with chain.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def test_machine_identity_created_and_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id="ed25519:test")
    assert identity["machine_role"] == "primary"
    assert identity["machine_id"]
    assert identity["signing_key_id"] == "ed25519:test"
    assert machine_identity_path(REPO).exists()

    loaded = load_machine_identity(REPO)
    assert loaded["machine_id"] == identity["machine_id"]
    again = ensure_machine_identity(REPO)
    assert again["machine_id"] == identity["machine_id"]


def test_add_machine_identity_fields_preserves_event_timestamp(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    identity = ensure_machine_identity(REPO, role="primary")
    record = {"timestamp_utc": "2026-05-06T12:00:00Z"}
    add_machine_identity_fields(record, REPO)
    assert record["machine_id"] == identity["machine_id"]
    assert record["machine_role"] == "primary"
    assert record["event_timestamp_utc"] == "2026-05-06T12:00:00Z"


def test_primary_registry_created_and_authorizes_local_machine(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id="ed25519:key1")
    registry = ensure_primary_machine_registry(
        REPO,
        identity=identity,
        public_key_fingerprint="ed25519:key1",
    )
    assert registry["registry_hash"].startswith("sha256:")
    assert machine_registry_path(REPO).exists()

    on_disk = json.loads(machine_registry_path(REPO).read_text(encoding="utf-8"))
    assert on_disk["registry_hash"] == registry["registry_hash"]
    loaded = load_machine_registry(REPO)
    assert loaded["registry_hash"] == registry["registry_hash"]

    authorized = authorized_machine_lookup(REPO, identity["machine_id"], "ed25519:key1")
    assert authorized is not None
    assert authorized["machine_id"] == identity["machine_id"]


def test_authorized_lookup_rejects_wrong_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id="ed25519:key1")
    ensure_primary_machine_registry(REPO, identity=identity, public_key_fingerprint="ed25519:key1")
    assert authorized_machine_lookup(REPO, identity["machine_id"], "ed25519:wrong") is None


def test_registry_add_remove_and_license_events(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    ensure_primary_machine_registry(REPO, identity=ensure_machine_identity(REPO, role="primary"))
    events = []

    registry, event = add_machine_to_registry(
        REPO,
        machine_id="remote-1",
        role="remote",
        display_name="Remote 1",
        public_key_fingerprint="ed25519:remote1",
        public_key_pem="-----BEGIN PUBLIC KEY-----\nmock\n-----END PUBLIC KEY-----\n",
        operator_confirmation_event_id="confirm-1",
        append_event=events.append,
    )
    _append_event_to_chain(tmp_path, events[-1])
    assert event is None
    assert events[-1]["event_type"] == "machine_added"
    assert events[-1]["subject_machine_id"] == "remote-1"
    assert events[-1]["registry_hash_after"] == registry["registry_hash"]
    assert authorized_machine_lookup(REPO, "remote-1", "ed25519:remote1") is not None

    registry, event = change_machine_license_status(
        REPO,
        "remote-1",
        "revoked",
        sync_authorized=False,
        append_event=events.append,
    )
    _append_event_to_chain(tmp_path, events[-1])
    assert events[-1]["event_type"] == "machine_license_status_changed"
    assert authorized_machine_lookup(REPO, "remote-1", "ed25519:remote1") is None

    registry, event = remove_machine_from_registry(REPO, "remote-1", reason="operator removal", append_event=events.append)
    _append_event_to_chain(tmp_path, events[-1])
    assert events[-1]["event_type"] == "machine_removed"
    assert events[-1]["license_status"] == "removed"


def test_registry_role_change_and_key_rotation_events(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    ensure_primary_machine_registry(REPO, identity=ensure_machine_identity(REPO, role="primary"))
    events = []
    add_machine_to_registry(
        REPO,
        machine_id="remote-2",
        role="remote",
        display_name="Remote 2",
        public_key_fingerprint="ed25519:old",
        public_key_pem="old pem",
        operator_confirmation_event_id="confirm-2",
        append_event=lambda event: _append_event_to_chain(tmp_path, event),
    )

    change_machine_role(REPO, "remote-2", "primary", append_event=events.append)
    _append_event_to_chain(tmp_path, events[-1])
    assert events[-1]["event_type"] == "machine_role_changed"
    assert events[-1]["from_role"] == "remote"
    assert events[-1]["to_role"] == "primary"

    rotate_machine_key(
        REPO,
        "remote-2",
        new_public_key_fingerprint="ed25519:new",
        new_public_key_pem="new pem",
        append_event=events.append,
    )
    _append_event_to_chain(tmp_path, events[-1])
    assert events[-1]["event_type"] == "machine_key_rotated"
    assert authorized_machine_lookup(REPO, "remote-2", "ed25519:new") is not None
    assert authorized_machine_lookup(REPO, "remote-2", "ed25519:old") is None


def test_forged_registry_without_chain_event_is_not_authorized(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    registry = {
        "registry_version": 1,
        "installation_id": "install-x",
        "machines": [{
            "machine_id": "evil-remote",
            "role": "remote",
            "display_name": "Evil",
            "public_key_fingerprint": "ed25519:evil",
            "license_status": "active",
            "sync_authorized": True,
            "operator_confirmed_utc": "2026-05-09T00:00:00Z",
            "operator_confirmation_event_id": "not-in-chain",
            "first_seen_utc": "2026-05-09T00:00:00Z",
            "last_sync_utc": None,
            "keys": [{
                "public_key_fingerprint": "ed25519:evil",
                "public_key_pem": "pem",
                "valid_from_utc": "2026-05-09T00:00:00Z",
                "valid_until_utc": None,
                "revoked_utc": None,
            }],
        }],
        "registry_hash": None,
    }
    from machine_identity import save_machine_registry
    save_machine_registry(REPO, registry)
    assert authorized_machine_lookup(REPO, "evil-remote", "ed25519:evil") is None
