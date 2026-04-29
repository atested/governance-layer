import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from chain_walker import (
    alert_reason,
    apply_walker_filters,
    is_alert_event,
    normalize_chain_line,
    normalize_record,
    normalize_records,
    walker_query,
)


def _mediated(decision="ALLOW", **extra):
    record = {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-04-27T12:00:00Z",
        "request_id": "req-1",
        "session_id": "sess-1",
        "user_identity": "cecil@example.com",
        "original_tool": "FS_READ",
        "classification": {
            "action_type": "read",
            "targets": ["/repo/README.md"],
            "scope": "project",
            "confidence_tier": 1,
        },
        "policy_decision": decision,
        "matched_rule": "allow_project_reads",
        "prev_record_hash": None,
        "record_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "signature": "sig",
        "signing_key_id": "key-1",
    }
    record.update(extra)
    return record


def test_mediated_allow_normalizes_and_renders_deterministically():
    row = normalize_record(_mediated(), sequence=7)

    assert row["sequence"] == 7
    assert row["category"] == "action_decision"
    assert row["decision"] == "ALLOW"
    assert row["action"] == "FS_READ"
    assert row["action_type"] == "read"
    assert row["target"] == "/repo/README.md"
    assert row["tier"] == "1"
    assert row["user"] == "cecil@example.com"
    assert row["hash"] == "sha256:aaaaaaaaaaaa"
    assert row["record_id"] == "req-1"
    assert row["signature_status"] == "signed"
    assert row["alert"] is False
    assert row["narrative"] == (
        "ALLOW: cecil@example.com ran FS_READ on /repo/README.md "
        "under rule allow_project_reads. Hash sha256:aaaaaaaaaaaa."
    )
    assert normalize_record(_mediated(), sequence=7)["narrative"] == row["narrative"]


def test_mediated_deny_is_an_alert_event():
    row = normalize_record(
        _mediated(
            "DENY",
            request_id="req-deny",
            original_tool="FS_DELETE",
            classification={
                "action_type": "delete",
                "targets": ["/prod/secrets.env"],
                "confidence_tier": 4,
            },
        ),
        sequence=8,
    )

    assert row["decision"] == "DENY"
    assert row["alert"] is True
    assert alert_reason(row) == "Policy denial"
    assert row["narrative"] == (
        "DENY: cecil@example.com attempted FS_DELETE on /prod/secrets.env. "
        "Policy denied before execution by rule allow_project_reads. Hash sha256:aaaaaaaaaaaa."
    )


def test_approval_and_revocation_records_alert_and_render():
    approval = normalize_record(
        {
            "event_type": "opaque_artifact_approval",
            "event_id": "evt-approve",
            "timestamp_utc": "2026-04-27T12:01:00Z",
            "artifact_identity": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "approving_operator": "greg@example.com",
            "governed_family": "network",
            "record_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        },
        sequence=9,
    )
    revocation = normalize_record(
        {
            "event_type": "opaque_artifact_revocation",
            "event_id": "evt-revoke",
            "timestamp_utc": "2026-04-27T12:02:00Z",
            "artifact_identity": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "revoking_operator": "greg@example.com",
            "governed_family": "network",
            "record_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        },
        sequence=10,
    )

    assert approval["category"] == "approval"
    assert approval["alert"] is True
    assert approval["alert_reason"] == "Approval recorded"
    assert approval["narrative"] == (
        "APPROVAL: operator greg@example.com approved artifact "
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb "
        "for future matching operations. Hash sha256:cccccccccccc."
    )
    assert revocation["category"] == "revocation"
    assert revocation["alert"] is True
    assert revocation["alert_reason"] == "Revocation recorded"
    assert revocation["narrative"] == (
        "REVOCATION: operator greg@example.com revoked approval "
        "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd; "
        "matching operations return to policy evaluation. Hash sha256:eeeeeeeeeeee."
    )


def test_integrity_events_and_license_events_are_classified_consistently():
    integrity = normalize_record(
        {
            "event_type": "policy_rules_changed",
            "event_id": "evt-policy",
            "timestamp_utc": "2026-04-27T12:03:00Z",
            "previous_policy_rules_hash": "sha256:old",
            "current_policy_rules_hash": "sha256:new",
            "record_hash": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        },
        sequence=11,
    )
    license_event = normalize_record(
        {
            "event_type": "license_revoked",
            "event_id": "evt-license",
            "timestamp_utc": "2026-04-27T12:04:00Z",
            "license_id": "lic-123",
            "record_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        },
        sequence=12,
    )

    assert integrity["category"] == "integrity"
    assert integrity["alert"] is True
    assert integrity["alert_reason"] == "Integrity event"
    assert integrity["narrative"] == (
        "INTEGRITY: policy rules changed (sha256:new). Hash sha256:ffffffffffff."
    )
    assert license_event["category"] == "license"
    assert is_alert_event(license_event) is True
    assert license_event["alert_reason"] == "License or machine state event"
    assert license_event["narrative"] == (
        "LICENSE: license revoked recorded for lic-123. Hash sha256:111111111111."
    )


def test_legacy_unsigned_records_are_supported_without_web_coupling():
    row = normalize_record(
        _mediated(
            signature=None,
            signing_key_id=None,
            record_version="0.2",
            tool="FS_WRITE",
            original_tool="",
        ),
        sequence=13,
    )

    assert row["signature_status"] == "unsigned_legacy"
    assert row["action"] == "FS_WRITE"
    assert row["alert"] is False
    assert row["narrative"] == (
        "ALLOW: cecil@example.com ran FS_WRITE on /repo/README.md "
        "under rule allow_project_reads. Hash sha256:aaaaaaaaaaaa."
    )


def test_malformed_records_become_alert_rows():
    bad_json = normalize_chain_line('{"event_type": ', sequence=14)
    bad_object = normalize_record(["not", "an", "object"], sequence=15)

    assert bad_json["category"] == "malformed"
    assert bad_json["alert"] is True
    assert bad_json["alert_reason"] == "Malformed chain record"
    assert bad_json["narrative"] == "MALFORMED: chain record 14 invalid JSON: Expecting value."
    assert bad_object["narrative"] == "MALFORMED: chain record 15 expected object, got list."


def test_normalize_records_and_filters_preserve_walker_semantics():
    rows = normalize_records(
        [
            _mediated("ALLOW", request_id="allow-1"),
            _mediated(
                "DENY",
                request_id="deny-1",
                classification={"action_type": "delete", "targets": ["/tmp/one"], "confidence_tier": 4},
            ),
        ],
        start_sequence=20,
    )

    assert [row["sequence"] for row in rows] == [20, 21]
    filtered = apply_walker_filters(rows, decision="DENY", action_type="delete", tier="4")
    assert len(filtered) == 1
    assert filtered[0]["record_id"] == "deny-1"


def test_walker_query_centers_live_chain_window(tmp_path):
    records = [
        _mediated("ALLOW", request_id=f"allow-{idx}", record_hash=f"sha256:{idx:064d}")
        for idx in range(12)
    ]
    records[6] = _mediated(
        "DENY",
        request_id="deny-center",
        record_hash="sha256:9999999999999999999999999999999999999999999999999999999999999999",
    )
    chain_path = tmp_path / "decision-chain.jsonl"
    chain_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )

    result = walker_query(chain_path, center_record_id="deny-center")

    assert result["chain_source"] == "live"
    assert result["total_matching"] == 12
    assert result["center_index"] == 6
    assert result["center_sequence"] == 7
    assert len(result["rows"]) == 11
    assert result["rows"][5]["record_id"] == "deny-center"
    assert result["rows"][5]["alert"] is True


def test_walker_query_jumps_to_next_and_previous_alert(tmp_path):
    records = [
        _mediated("ALLOW", request_id=f"allow-{idx}", record_hash=f"sha256:{idx:064d}")
        for idx in range(9)
    ]
    records[2] = _mediated("DENY", request_id="deny-earlier", record_hash="sha256:" + "2" * 64)
    records[7] = _mediated("DENY", request_id="deny-later", record_hash="sha256:" + "7" * 64)
    chain_path = tmp_path / "decision-chain.jsonl"
    chain_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )

    next_alert = walker_query(chain_path, center_index=3, alert_direction="next")
    previous_alert = walker_query(chain_path, center_index=6, alert_direction="previous")

    assert next_alert["alert_jump_found"] is True
    assert next_alert["center_index"] == 7
    assert next_alert["center_sequence"] == 8
    assert next(row for row in next_alert["rows"] if row["sequence"] == 8)["record_id"] == "deny-later"
    assert previous_alert["alert_jump_found"] is True
    assert previous_alert["center_index"] == 2
    assert previous_alert["center_sequence"] == 3
    assert next(row for row in previous_alert["rows"] if row["sequence"] == 3)["record_id"] == "deny-earlier"


# ---------------------------------------------------------------------------
# SEC-2026-007: Invalid archive IDs must fail, not fall back to live chain
# ---------------------------------------------------------------------------

from chain_walker import load_raw_records_range


def test_invalid_archive_id_returns_error(tmp_path):
    """An invalid archive_id must return an error, not live chain data."""
    chain_path = tmp_path / "decision-chain.jsonl"
    chain_path.write_text(
        json.dumps(_mediated("ALLOW", request_id="live-1"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = load_raw_records_range(
        chain_path,
        start_sequence=1,
        end_sequence=1,
        chain_source="archive",
        archive_id="nonexistent-archive",
    )
    assert "error" in result
    assert "nonexistent-archive" in result["error"]
    assert result["record_count"] == 0


def test_missing_archive_id_returns_error(tmp_path):
    """chain_source='archive' without archive_id must return an error."""
    chain_path = tmp_path / "decision-chain.jsonl"
    chain_path.write_text(
        json.dumps(_mediated("ALLOW", request_id="live-1"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = load_raw_records_range(
        chain_path,
        start_sequence=1,
        end_sequence=1,
        chain_source="archive",
        archive_id="",
    )
    assert "error" in result
    assert result["record_count"] == 0


def test_walker_query_invalid_archive_returns_error(tmp_path):
    """walker_query with invalid archive returns error, not live chain."""
    chain_path = tmp_path / "decision-chain.jsonl"
    chain_path.write_text(
        json.dumps(_mediated("ALLOW", request_id="live-1"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = walker_query(chain_path, chain_source="archive", archive_id="bad-id")
    assert "error" in result
    assert result["total_matching"] == 0
