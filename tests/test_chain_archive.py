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

    assert chain_path.exists() is False
    archive_path = Path(manifest["archive_chain_path"])
    assert archive_path.exists()
    assert archive_path.read_text(encoding="utf-8").count("\n") == 2
    assert manifest["record_count"] == 2
    assert manifest["last_record_hash"] == "sha256:" + "2" * 64
    assert manifest["chain_existed"] is True
    assert manifest["sidecar_only_terminal_event"] is True

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
    manifest = archive_chain(chain_path, reason="startup_integrity_violation")

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
