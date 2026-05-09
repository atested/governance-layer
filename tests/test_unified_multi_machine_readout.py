"""Tests for Layer 3 multi-machine unified readout and evidence export."""

import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from event_model import build_non_action_event, sign_non_action_event  # noqa: E402
from evidence_package import decrypt_payload, build_package  # noqa: E402
from machine_identity import add_machine_to_registry, ensure_machine_identity, ensure_primary_machine_registry  # noqa: E402
from readout import audit_query, audit_report, governance_activity_view  # noqa: E402
from remote_import import CURRENT_CHAIN_SEGMENT, import_remote_segment  # noqa: E402
from sync_protocol import private_key_fingerprint, private_key_public_pem  # noqa: E402
from unified_readout import load_unified_records, selected_import_context  # noqa: E402


def _append_event_to_chain(chain: Path, event: dict) -> dict:
    chain.parent.mkdir(parents=True, exist_ok=True)
    with chain.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def _setup_imported_remote(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    primary_key = Ed25519PrivateKey.generate()
    remote_key = Ed25519PrivateKey.generate()
    primary_id = private_key_fingerprint(primary_key)
    remote_key_id = private_key_fingerprint(remote_key)
    primary_identity = ensure_machine_identity(REPO, role="primary", signing_key_id=primary_id)
    ensure_primary_machine_registry(
        REPO,
        identity=primary_identity,
        public_key_fingerprint=primary_id,
        public_key_pem=private_key_public_pem(primary_key),
    )
    chain = runtime / "LOGS" / "decision-chain.jsonl"
    add_machine_to_registry(
        REPO,
        machine_id="remote-e-1",
        role="remote",
        display_name="Remote E",
        public_key_fingerprint=remote_key_id,
        public_key_pem=private_key_public_pem(remote_key),
        operator_confirmation_event_id="confirm-e-1",
        append_event=lambda event: _append_event_to_chain(chain, event),
    )

    primary_event = build_non_action_event(
        "usage_attestation",
        {
            "summary": "primary local event",
            "machine_id": primary_identity["machine_id"],
            "machine_role": "primary",
        },
        signing_key=primary_key,
        signing_key_id=primary_id,
    )
    _append_event_to_chain(chain, primary_event)

    remote_event = build_non_action_event(
        "usage_attestation",
        {
            "summary": "remote imported event",
            "machine_id": "remote-e-1",
            "machine_role": "remote",
        },
        prev_record_hash=None,
    )
    sign_non_action_event(remote_event, remote_key, remote_key_id)
    raw = (json.dumps(remote_event, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    result = import_remote_segment(
        REPO,
        source_machine_id="remote-e-1",
        segment_kind=CURRENT_CHAIN_SEGMENT,
        records_jsonl=raw,
        sync_session_id="sync-e-1",
        signing_key=primary_key,
        signing_key_id=primary_id,
    )
    assert result.accepted
    return {
        "runtime": runtime,
        "chain": chain,
        "primary_machine_id": primary_identity["machine_id"],
        "remote_machine_id": "remote-e-1",
        "remote_record_hash": remote_event["record_hash"],
        "import_envelope_hash": result.import_envelope_hash,
    }


def test_unified_records_merge_primary_and_verified_remote(tmp_path, monkeypatch):
    ctx = _setup_imported_remote(tmp_path, monkeypatch)
    records, meta = load_unified_records(REPO, ctx["chain"])
    remote_records = [record for record in records if record.get("_unified_source") == "remote_import"]
    assert len(remote_records) == 1
    assert remote_records[0]["machine_id"] == ctx["remote_machine_id"]
    assert remote_records[0]["event_timestamp_utc"]
    assert remote_records[0]["primary_import_timestamp_utc"]
    assert remote_records[0]["import_envelope_hash"] == ctx["import_envelope_hash"]
    assert meta["imported_record_count"] == 1
    assert meta["sidecars"][0]["stored_segment_sha256"].startswith("sha256:")


def test_machine_filters_apply_to_activity_audit_and_reports(tmp_path, monkeypatch):
    ctx = _setup_imported_remote(tmp_path, monkeypatch)
    activity = governance_activity_view(ctx["chain"], machine_ids=[ctx["remote_machine_id"]])
    assert activity["total_matching"] == 1
    assert activity["entries"][0]["machine_id"] == ctx["remote_machine_id"]
    assert activity["entries"][0]["primary_import_timestamp_utc"]

    query = audit_query(ctx["chain"], ctx["runtime"] / "LOGS" / "records", machine_scope="primary")
    assert all(entry["machine_role"] == "primary" for entry in query["entries"])

    report = audit_report(ctx["chain"], ctx["runtime"] / "LOGS" / "records", group_by="tool", machine_ids=[ctx["remote_machine_id"]])
    assert report["total_records"] == 1
    assert report["unified_view"]["imported_record_count"] == 1


def test_evidence_package_includes_machine_scope_import_context(tmp_path, monkeypatch):
    ctx = _setup_imported_remote(tmp_path, monkeypatch)
    records, _meta = load_unified_records(REPO, ctx["chain"], machine_ids=[ctx["remote_machine_id"]])
    import_context = selected_import_context(REPO, records)
    package = build_package(
        records=records,
        password="Correct horse battery staple 1!",
        operator_identity="test-operator",
        start_sequence=1,
        end_sequence=len(records),
        multi_machine_context=import_context,
        machine_scope="selected",
        machine_ids=[ctx["remote_machine_id"]],
    )
    assert package["manifest"]["machine_scope"]["mode"] == "selected"
    assert package["manifest"]["machine_scope"]["machine_ids"] == [ctx["remote_machine_id"]]
    assert package["manifest"]["machine_scope"]["import_envelope_count"] == 1

    zip_path = tmp_path / "package.zip"
    zip_path.write_bytes(package["zip_bytes"])
    with zipfile.ZipFile(zip_path, "r") as zf:
        encrypted = zf.read("atested-evidence-package/encrypted-chain.bin")
        manifest = json.loads(zf.read("atested-evidence-package/manifest.json").decode("utf-8"))
    plaintext = json.loads(decrypt_payload(
        encrypted[:-16],
        encrypted[-16:],
        bytes.fromhex(manifest["encryption"]["nonce_hex"]),
        bytes.fromhex(manifest["encryption"]["salt_hex"]),
        "Correct horse battery staple 1!",
        manifest["encryption"]["iterations"],
    ).decode("utf-8"))
    mm = plaintext["multi_machine_context"]
    assert mm["machine_registry_snapshot"]["machines"]
    assert mm["import_envelopes"][0]["record_hash"] == ctx["import_envelope_hash"]
    assert mm["remote_sidecar_hashes"][0]["stored_segment_sha256"].startswith("sha256:")
