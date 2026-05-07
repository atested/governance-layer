"""Tests for v1 multi-machine sync transport."""

import json
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from event_model import build_non_action_event, sign_non_action_event  # noqa: E402
from machine_identity import (  # noqa: E402
    add_machine_to_registry,
    ensure_machine_identity,
    ensure_primary_machine_registry,
    remove_machine_from_registry,
)
from remote_import import CURRENT_CHAIN_SEGMENT, compute_segment_id  # noqa: E402
from sync_client import SyncClient, SyncClientError  # noqa: E402
from sync_protocol import (  # noqa: E402
    SyncTriggerManager,
    b64encode,
    private_key_fingerprint,
    private_key_public_pem,
    now_utc_z,
    sha256_bytes,
    sign_segment_request,
    sign_response,
    verify_response_signature,
)
from sync_service import SyncHTTPRequestHandler, SyncService, _SyncHTTPServer  # noqa: E402


@pytest.fixture
def keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    return priv, private_key_fingerprint(priv), private_key_public_pem(priv)


def _setup_primary(monkeypatch, tmp_path, primary_keypair, remote_keypair, *, remote_id="remote-sync-1"):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    primary_priv, primary_key_id, primary_pem = primary_keypair
    _, remote_key_id, remote_pem = remote_keypair
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id=primary_key_id)
    ensure_primary_machine_registry(
        REPO,
        identity=identity,
        public_key_fingerprint=primary_key_id,
        public_key_pem=primary_pem,
    )
    add_machine_to_registry(
        REPO,
        machine_id=remote_id,
        role="remote",
        display_name="Remote Sync",
        public_key_fingerprint=remote_key_id,
        public_key_pem=remote_pem,
        operator_confirmation_event_id="confirm-sync-1",
    )
    logs = tmp_path / "runtime" / "LOGS"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "update_notifications.jsonl").write_text(
        json.dumps({"notification_id": "n1", "version": "9.9.9"}) + "\n",
        encoding="utf-8",
    )
    return primary_priv, primary_key_id, primary_pem


@pytest.fixture
def sync_server(monkeypatch, tmp_path, keypair):
    primary_keypair = keypair
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    remote_priv = Ed25519PrivateKey.generate()
    remote_keypair = (remote_priv, private_key_fingerprint(remote_priv), private_key_public_pem(remote_priv))
    primary_priv, primary_key_id, primary_pem = _setup_primary(monkeypatch, tmp_path, primary_keypair, remote_keypair)
    service = SyncService(REPO, primary_private_key=primary_priv, primary_signing_key_id=primary_key_id)
    server = _SyncHTTPServer(("127.0.0.1", 0), SyncHTTPRequestHandler, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "url": f"http://127.0.0.1:{server.server_address[1]}",
            "remote_private_key": remote_priv,
            "primary_public_key_pem": primary_pem,
            "remote_machine_id": "remote-sync-1",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _remote_event(remote_private_key, summary: str, *, prev_hash=None, machine_id="remote-sync-1"):
    event = build_non_action_event(
        "usage_attestation",
        {
            "summary": summary,
            "machine_id": machine_id,
            "machine_role": "remote",
        },
        prev_record_hash=prev_hash,
    )
    sign_non_action_event(event, remote_private_key, private_key_fingerprint(remote_private_key))
    return event


def _jsonl(records):
    return ("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records) + "\n").encode("utf-8")


def test_client_handshake_segment_sync_and_state_bundle(sync_server, tmp_path, monkeypatch):
    client = SyncClient(
        REPO,
        sync_server["url"],
        remote_private_key=sync_server["remote_private_key"],
        source_machine_id=sync_server["remote_machine_id"],
        primary_public_key_pem=sync_server["primary_public_key_pem"],
    )
    session = client.start_session()
    assert session["accepted"]
    assert session["nonce"]

    first = _remote_event(sync_server["remote_private_key"], "first")
    second = _remote_event(sync_server["remote_private_key"], "second", prev_hash=first["record_hash"])
    response = client.sync_current_segment(_jsonl([first, second]))

    assert response["accepted"]
    assert response["import_envelope_hash"].startswith("sha256:")
    assert response["approval_store_hash"].startswith("sha256:")
    assert response["policy_rules_hash"].startswith("sha256:")
    assert response["communications"][0]["notification_id"] == "n1"
    assert (tmp_path / "runtime" / "sync" / "state_bundle.json").exists()


def test_unknown_machine_rejects_segment(monkeypatch, tmp_path, keypair):
    primary_keypair = keypair
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    remote_priv = Ed25519PrivateKey.generate()
    primary_priv, primary_key_id, _ = primary_keypair
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    ensure_primary_machine_registry(REPO, identity=ensure_machine_identity(REPO, role="primary", signing_key_id=primary_key_id))
    service = SyncService(REPO, primary_private_key=primary_priv, primary_signing_key_id=primary_key_id)
    status, session = service.start_session({
        "source_machine_id": "unknown-remote",
        "source_machine_key_id": private_key_fingerprint(remote_priv),
    })
    record = _remote_event(remote_priv, "unknown", machine_id="unknown-remote")
    payload = _signed_segment_payload(session, remote_priv, "unknown-remote", _jsonl([record]))
    status, response = service.receive_segment(payload)
    assert status == 403
    assert response["error"] == "MACHINE_NOT_AUTHORIZED"


def test_removed_machine_rejects_segment(monkeypatch, tmp_path, keypair):
    primary_keypair = keypair
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    remote_priv = Ed25519PrivateKey.generate()
    remote_keypair = (remote_priv, private_key_fingerprint(remote_priv), private_key_public_pem(remote_priv))
    primary_priv, primary_key_id, _ = _setup_primary(monkeypatch, tmp_path, primary_keypair, remote_keypair)
    remove_machine_from_registry(REPO, "remote-sync-1")
    service = SyncService(REPO, primary_private_key=primary_priv, primary_signing_key_id=primary_key_id)
    _, session = service.start_session({
        "source_machine_id": "remote-sync-1",
        "source_machine_key_id": private_key_fingerprint(remote_priv),
    })
    record = _remote_event(remote_priv, "removed")
    payload = _signed_segment_payload(session, remote_priv, "remote-sync-1", _jsonl([record]))
    status, response = service.receive_segment(payload)
    assert status == 403
    assert response["error"] == "MACHINE_NOT_AUTHORIZED"


def test_replay_request_number_rejected(monkeypatch, tmp_path, keypair):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    remote_priv = Ed25519PrivateKey.generate()
    remote_keypair = (remote_priv, private_key_fingerprint(remote_priv), private_key_public_pem(remote_priv))
    primary_priv, primary_key_id, _ = _setup_primary(monkeypatch, tmp_path, keypair, remote_keypair)
    service = SyncService(REPO, primary_private_key=primary_priv, primary_signing_key_id=primary_key_id)
    _, session = service.start_session({
        "source_machine_id": "remote-sync-1",
        "source_machine_key_id": private_key_fingerprint(remote_priv),
    })
    record = _remote_event(remote_priv, "replay")
    payload = _signed_segment_payload(session, remote_priv, "remote-sync-1", _jsonl([record]), request_number=1)
    assert service.receive_segment(payload)[0] == 200
    status, response = service.receive_segment(payload)
    assert status == 409
    assert response["error"] == "REQUEST_NUMBER_REPLAY"


def test_duplicate_retry_with_new_request_number_is_idempotent(sync_server):
    client = SyncClient(
        REPO,
        sync_server["url"],
        remote_private_key=sync_server["remote_private_key"],
        source_machine_id=sync_server["remote_machine_id"],
        primary_public_key_pem=sync_server["primary_public_key_pem"],
    )
    record = _remote_event(sync_server["remote_private_key"], "dup")
    raw = _jsonl([record])
    first = client.sync_current_segment(raw)
    retry = client.sync_current_segment(raw)
    assert retry["accepted"]
    assert retry["duplicate"]
    assert retry["import_envelope_hash"] == first["import_envelope_hash"]


def test_response_signature_tamper_detection(keypair):
    private_key, _, public_pem = keypair
    response = sign_response("/sync/v1/segment", {"accepted": True, "segment_id": "s1"}, private_key)
    assert verify_response_signature("/sync/v1/segment", response, public_pem)
    response["segment_id"] = "tampered"
    assert not verify_response_signature("/sync/v1/segment", response, public_pem)


def test_sync_trigger_manager_baseline_and_backoff():
    triggers = SyncTriggerManager(baseline_interval_seconds=300)
    assert triggers.due_triggers(1000) == ["remote_startup"]
    triggers.mark_success(1000)
    assert triggers.due_triggers(1200) == []
    assert triggers.due_triggers(1301) == ["periodic_baseline"]
    triggers.request_sync("approval_store_changed")
    assert triggers.due_triggers(1302) == ["approval_store_changed"]
    triggers.mark_failure()
    assert triggers.next_delay_seconds() == 30
    triggers.mark_failure()
    assert triggers.next_delay_seconds() == 120


def test_client_rejects_tampered_primary_response(sync_server):
    client = SyncClient(
        REPO,
        sync_server["url"],
        remote_private_key=sync_server["remote_private_key"],
        source_machine_id=sync_server["remote_machine_id"],
        primary_public_key_pem="bad pem",
    )
    with pytest.raises(SyncClientError, match="PRIMARY_SIGNATURE_INVALID"):
        client.start_session()


def _signed_segment_payload(session, remote_private_key, machine_id, raw, *, request_number=1):
    stored_sha = sha256_bytes(raw)
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    segment_id = compute_segment_id(
        machine_id,
        CURRENT_CHAIN_SEGMENT,
        records[0]["record_hash"],
        records[-1]["record_hash"],
        len(records),
        stored_sha,
    )
    payload = {
        "sync_session_id": session["sync_session_id"],
        "request_number": request_number,
        "timestamp_utc": now_utc_z(),
        "source_machine_id": machine_id,
        "segment_id": segment_id,
        "segment_kind": CURRENT_CHAIN_SEGMENT,
        "segment_sha256": stored_sha,
        "records_jsonl_b64": b64encode(raw),
        "archive_manifest": None,
    }
    return sign_segment_request("POST", "/sync/v1/segment", payload, session["nonce"], remote_private_key)
