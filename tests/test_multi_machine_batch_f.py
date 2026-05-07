"""Batch F coverage for telemetry aggregation, relay, versions, and restore."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from event_model import build_non_action_event  # noqa: E402
from machine_identity import ensure_machine_identity, ensure_primary_machine_registry  # noqa: E402
from multi_machine_ops import (  # noqa: E402
    apply_machine_coverage_to_telemetry_artifact,
    normalize_communications,
    store_remote_telemetry_summary,
    telemetry_submission_event_payload,
    validate_primary_restore_runtime,
)
from proxy.server import ChainRecorder  # noqa: E402
from sync_protocol import private_key_fingerprint, private_key_public_pem, sha256_json  # noqa: E402


def test_primary_telemetry_artifact_includes_remote_machine_coverage(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id="ed25519:primary")
    local_summary = {"schema_version": 1, "lifetime": {"flushes": 2}, "periods": {}}
    telemetry_dir = tmp_path / "runtime" / "LOGS" / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    (telemetry_dir / "summary.json").write_text(json.dumps(local_summary), encoding="utf-8")

    remote_summary = {"schema_version": 1, "lifetime": {"flushes": 4}, "periods": {}}
    stored = store_remote_telemetry_summary(
        REPO,
        "remote-telemetry-1",
        {"machine_role": "remote", "summary": remote_summary, "summary_hash": sha256_json(remote_summary)},
    )
    assert stored["summary_hash"].startswith("sha256:")

    artifact = {
        "artifact_type": "anonymous_summary_telemetry",
        "artifact_id": "tm_test",
        "artifact_hash": "sha256:placeholder",
        "summary": local_summary,
    }
    enriched = apply_machine_coverage_to_telemetry_artifact(REPO, artifact)
    coverage_ids = {item["machine_id"] for item in enriched["machine_coverage"]}
    assert identity["machine_id"] in coverage_ids
    assert "remote-telemetry-1" in coverage_ids
    assert enriched["machine_coverage_count"] == 2

    event_payload = telemetry_submission_event_payload("https://license.atested.com/api/telemetry", enriched)
    assert event_payload["payload_hash"] == enriched["artifact_hash"]
    assert event_payload["machine_coverage_count"] == 2


def test_communications_relay_uses_stable_message_ids_and_deduplicates():
    messages = normalize_communications([
        {"notification_id": "n1", "message": "Version 1"},
        {"notification_id": "n1", "message": "Version 1 duplicate"},
        {"request_id": "support-1", "message": "Support"},
        {"message": "No ID"},
        {"message": "No ID"},
    ])
    assert [msg["message_id"] for msg in messages[:2]] == ["n1", "support-1"]
    assert len(messages) == 3
    assert messages[2]["message_id"].startswith("sha256:")


def test_restore_runtime_validation_accepts_required_primary_contents(tmp_path, monkeypatch):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(tmp_path / "runtime"))
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "runtime" / ".atested-signing-key.pem"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    key_id = private_key_fingerprint(private_key)
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id=key_id)
    ensure_primary_machine_registry(
        REPO,
        identity=identity,
        public_key_fingerprint=key_id,
        public_key_pem=private_key_public_pem(private_key),
    )
    chain_path = tmp_path / "runtime" / "LOGS" / "decision-chain.jsonl"
    event = build_non_action_event("usage_attestation", {"summary": "restore validation"})
    ChainRecorder(chain_path).append_atomic(event)

    result = validate_primary_restore_runtime(REPO, runtime=tmp_path / "runtime")
    assert result["restore_runtime_valid"] is True
    assert any(check["name"] == "chain_integrity" and check["status"] == "ok" for check in result["checks"])
