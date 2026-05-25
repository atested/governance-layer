import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from scripts.event_model import build_non_action_event
from proxy.server import ChainRecorder
from chain_archive import archive_chain, list_archives
from chain_walker import walker_query


def _record(event_type, event_id, record_hash):
    return {
        "event_type": event_type,
        "event_id": event_id,
        "timestamp_utc": "2026-04-27T12:00:00Z",
        "user_identity": "greg@example.com",
        "record_hash": record_hash,
    }


def _write_chain(path, records):
    path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


def test_archive_chain_moves_chain_writes_manifest_and_sidecar_event(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    sidecar_path = tmp_path / "integrity-events.jsonl"
    records = [
        _record("proxy_startup_code_hash", "evt-1", "sha256:" + "1" * 64),
        _record("policy_rules_changed", "evt-2", "sha256:" + "2" * 64),
    ]
    _write_chain(chain_path, records)

    manifest = archive_chain(
        chain_path,
        reason="chain_integrity_violation",
        payload={"detail": "tail hash mismatch"},
        sidecar_events_path=sidecar_path,
    )

    # The archived copy preserves the original records...
    archive_path = Path(manifest["archive_chain_path"])
    assert archive_path.exists()
    assert archive_path.read_text(encoding="utf-8").count("\n") == 2
    assert manifest["record_count"] == 2
    assert manifest["last_record_hash"] == "sha256:" + "2" * 64
    assert manifest["chain_existed"] is True
    assert manifest["sidecar_only_terminal_event"] is True

    # ...and the live chain is never left missing: it now holds a single
    # chain_started_after_archive provenance record documenting the archive.
    assert chain_path.exists()
    genesis = json.loads(chain_path.read_text(encoding="utf-8").strip())
    assert genesis["event_type"] == "chain_started_after_archive"
    assert genesis["archive_reason"] == "chain_integrity_violation"
    assert genesis["archived_record_count"] == 2
    assert genesis["prior_chain_last_hash"] == "sha256:" + "2" * 64
    assert genesis["archive_manifest_path"] == manifest["manifest_path"]
    assert genesis["archive_manifest_hash"].startswith("sha256:")
    assert genesis["prev_record_hash"] is None
    assert genesis["record_hash"] == manifest["genesis_record_hash"]

    listed = list_archives(chain_path)
    assert [item["archive_id"] for item in listed] == [manifest["archive_id"]]

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8").strip())
    assert sidecar["event_type"] == "chain_archived_after_integrity_violation"
    assert sidecar["archive_id"] == manifest["archive_id"]
    assert sidecar["reason"] == "chain_integrity_violation"


def test_walker_query_reads_archived_chain_source(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    records = [
        _record("proxy_startup_code_hash", "evt-start", "sha256:" + "a" * 64),
        _record("policy_rules_changed", "evt-policy", "sha256:" + "b" * 64),
    ]
    _write_chain(chain_path, records)
    manifest = archive_chain(chain_path, reason="policy_rules_changed")

    result = walker_query(
        chain_path,
        chain_source="archive",
        archive_id=manifest["archive_id"],
        center_record_id="evt-policy",
    )

    assert result["chain_source"] == "archive"
    assert result["archive"]["archive_id"] == manifest["archive_id"]
    assert result["total_matching"] == 2
    assert result["center_sequence"] == 2
    assert result["rows"][1]["record_id"] == "evt-policy"
    assert result["rows"][1]["alert"] is True


def test_fresh_chain_can_record_archive_reference_event(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    _write_chain(chain_path, [_record("chain_file_truncated", "evt-bad", "sha256:" + "c" * 64)])
    # write_genesis=False: this models the proxy startup path, where the proxy
    # appends its own signed genesis after archiving (archive_chain must not
    # also write one, or the chain would carry two genesis records).
    manifest = archive_chain(chain_path, reason="startup_integrity_violation", write_genesis=False)
    assert chain_path.exists() is False

    recorder = ChainRecorder(chain_path)
    event = recorder.append_integrity_event(
        "chain_started_after_archive",
        {
            "archive_id": manifest["archive_id"],
            "archive_manifest_path": manifest["manifest_path"],
            "archive_chain_path": manifest["archive_chain_path"],
            "reason": manifest["reason"],
        },
    )

    assert chain_path.exists()
    assert event["event_type"] == "chain_started_after_archive"
    assert event["archive_id"] == manifest["archive_id"]
    stored = json.loads(chain_path.read_text(encoding="utf-8").strip())
    assert stored["event_type"] == "chain_started_after_archive"


def test_chain_started_after_archive_event_type_is_buildable():
    event = build_non_action_event("chain_started_after_archive", {"archive_id": "archive-1"})

    assert event["event_type"] == "chain_started_after_archive"
    assert event["archive_id"] == "archive-1"
    assert event["machine_id"]
    assert event["machine_role"]
    assert event["event_timestamp_utc"]
    assert event["approval_store_hash"].startswith("sha256:")
    assert event["policy_rules_hash"].startswith("sha256:")


def test_qa_chain_genesis_is_signed_and_continues_sequence(tmp_path):
    """A signed genesis for the QA chain must verify and continue the sequence.

    The Rust quality service re-verifies the QA chain's record_hash on startup
    using the shared canonical form, and resumes at genesis.sequence + 1. This
    asserts the Python-written genesis is hash-valid, signed with the chain's
    own key (matching key_id), and carries a continued sequence.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sys.path.insert(0, str(REPO / "scripts"))
    from receipt_signing import _public_key_fingerprint
    from cryptography.hazmat.primitives import serialization
    from event_model import verify_non_action_event_hash

    priv = Ed25519PrivateKey.generate()
    key_id = _public_key_fingerprint(priv.public_key(), serialization)

    chain_path = tmp_path / "qa-chain.jsonl"
    # A QA-style chain whose last record carries a monotonic sequence.
    last = _record("policy_rules_changed", "evt-seq", "sha256:" + "e" * 64)
    last["sequence"] = 41
    _write_chain(chain_path, [last])

    manifest = archive_chain(
        chain_path,
        reason="qa_chain_env005_hash_linkage_corruption",
        signing_key=priv,
        signing_key_id=key_id,
    )

    genesis = json.loads(chain_path.read_text(encoding="utf-8").strip())
    assert genesis["event_type"] == "chain_started_after_archive"
    assert genesis["sequence"] == 42  # 41 + 1
    assert genesis["signing_key_id"] == key_id
    assert genesis["signature"]
    ok, err = verify_non_action_event_hash(genesis)
    assert ok, err
