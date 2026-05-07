"""Tests for local machine identity and registry bootstrap."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from machine_identity import (  # noqa: E402
    add_machine_identity_fields,
    authorized_machine_lookup,
    ensure_machine_identity,
    ensure_primary_machine_registry,
    load_machine_identity,
    load_machine_registry,
    machine_identity_path,
    machine_registry_path,
)


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
