"""Tests for multi-machine remote segment import infrastructure."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from event_model import build_non_action_event, sign_non_action_event  # noqa: E402
from machine_identity import add_machine_to_registry, ensure_machine_identity, ensure_primary_machine_registry  # noqa: E402
from receipt_signing import _public_key_fingerprint  # noqa: E402
from remote_import import (  # noqa: E402
    CURRENT_CHAIN_SEGMENT,
    compute_segment_id,
    import_remote_segment,
    segment_paths,
    sha256_bytes,
    verify_remote_segment,
    verify_stored_segment_binding,
)


@pytest.fixture
def remote_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    key_id = _public_key_fingerprint(pub, serialization)
    pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv, key_id, pem


def _setup_registry(monkeypatch, tmp_path, remote_keypair):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    ensure_primary_machine_registry(REPO, identity=ensure_machine_identity(REPO, role="primary"))
    _, key_id, public_pem = remote_keypair
    add_machine_to_registry(
        REPO,
        machine_id="remote-machine-1",
        role="remote",
        display_name="Remote",
        public_key_fingerprint=key_id,
        public_key_pem=public_pem,
        operator_confirmation_event_id="confirm-remote-machine-1",
    )


def _remote_event(remote_keypair, event_id: str, prev_hash=None, machine_id="remote-machine-1"):
    priv, key_id, _ = remote_keypair
    event = build_non_action_event(
        "usage_attestation",
        {
            "summary": event_id,
            "machine_id": machine_id,
            "machine_role": "remote",
        },
        prev_record_hash=prev_hash,
    )
    sign_non_action_event(event, priv, key_id)
    return event


def _jsonl(records):
    return ("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records) + "\n").encode("utf-8")


def test_valid_remote_segment_imports_sidecar_and_envelope(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    first = _remote_event(remote_keypair, "first")
    second = _remote_event(remote_keypair, "second", prev_hash=first["record_hash"])
    raw = _jsonl([first, second])

    result = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw,
        sync_session_id="sync-test-1",
    )

    assert result.accepted
    assert not result.duplicate
    assert result.envelope["event_type"] == "remote_chain_import"
    assert result.envelope["verification_result"] == "PASS"
    assert result.envelope["remote_record_count"] == 2
    sidecar_path, manifest_path = segment_paths(REPO, "remote-machine-1", result.segment_id)
    assert sidecar_path.read_bytes() == raw
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["import_envelope_hash"] == result.import_envelope_hash
    ok, err = verify_stored_segment_binding(REPO, result.envelope)
    assert ok, err


def test_broken_linkage_rejects_segment(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    first = _remote_event(remote_keypair, "first")
    second = _remote_event(remote_keypair, "second", prev_hash="sha256:" + "1" * 64)
    raw = _jsonl([first, second])

    result = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw,
        sync_session_id="sync-test-2",
    )

    assert not result.accepted
    assert any("PREV_RECORD_HASH_MISMATCH" in err for err in result.errors)


def test_wrong_machine_id_rejects_segment(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    record = _remote_event(remote_keypair, "wrong-machine", machine_id="other-machine")
    result = verify_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        records_jsonl=_jsonl([record]),
    )
    assert not result.ok
    assert any("MACHINE_ID_MISMATCH" in err for err in result.errors)


def test_bad_signature_rejects_segment(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    record = _remote_event(remote_keypair, "bad-signature")
    record["signature"] = "A" * len(record["signature"])

    result = verify_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        records_jsonl=_jsonl([record]),
    )
    assert not result.ok
    assert any("SIGNATURE_INVALID" in err for err in result.errors)


def test_duplicate_retry_is_idempotent_and_body_conflict_rejects(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    record = _remote_event(remote_keypair, "retry")
    raw = _jsonl([record])
    stored_hash = sha256_bytes(raw)
    segment_id = compute_segment_id(
        "remote-machine-1",
        CURRENT_CHAIN_SEGMENT,
        record["record_hash"],
        record["record_hash"],
        1,
        stored_hash,
    )

    first = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw,
        sync_session_id="sync-test-3",
        segment_id=segment_id,
    )
    retry = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw,
        sync_session_id="sync-test-3",
        segment_id=segment_id,
    )
    conflict = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw + b"\n",
        sync_session_id="sync-test-3",
        segment_id=segment_id,
    )

    assert first.accepted
    assert retry.accepted
    assert retry.duplicate
    assert retry.import_envelope_hash == first.import_envelope_hash
    assert not conflict.accepted
    assert conflict.errors == ("SEGMENT_ID_BODY_CONFLICT",)


def test_sidecar_tamper_is_detected(tmp_path, monkeypatch, remote_keypair):
    _setup_registry(monkeypatch, tmp_path, remote_keypair)
    record = _remote_event(remote_keypair, "tamper")
    result = import_remote_segment(
        REPO,
        source_machine_id="remote-machine-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=_jsonl([record]),
        sync_session_id="sync-test-4",
    )
    sidecar_path, _ = segment_paths(REPO, "remote-machine-1", result.segment_id)
    sidecar_path.write_text("{}\n", encoding="utf-8")

    ok, err = verify_stored_segment_binding(REPO, result.envelope)
    assert not ok
    assert "STORED_SEGMENT_SHA256_MISMATCH" in err
