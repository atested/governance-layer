import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard"))

from conformance import DashboardQAChainReader, build_conformance_payload


def test_conformance_mode2_active_when_decision_verifications_exist(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_decision_verification",
                "sequence": 2,
                "governance_record_hash": "sha256:" + "c" * 64,
                "decision_type": "ALLOW",
                "tool_name": "Read",
                "checks_performed": {"structural_integrity": "pass"},
                "all_clear": True,
            },
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "verified"
    assert payload["modes"]["post_hoc"]["status"] == "active"
    assert payload["modes"]["post_hoc"]["decisions_verified"] == 1
    assert payload["modes"]["post_hoc"]["last_verified_record_hash"] == "sha256:" + "c" * 64


def test_conformance_mode2_finding_when_decision_verification_fails(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_decision_verification",
                "sequence": 2,
                "governance_record_hash": "sha256:" + "d" * 64,
                "decision_type": "ALLOW",
                "tool_name": "Write",
                "checks_performed": {"negative_constraints": {"status": "fail"}},
                "all_clear": False,
                "findings": [{"check": "negative_constraints", "severity": "critical"}],
            },
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "attention"
    assert payload["modes"]["post_hoc"]["status"] == "finding"
    assert payload["modes"]["post_hoc"]["findings"][0]["check"] == "negative_constraints"


def test_conformance_mode2_behind_when_backlog_warning_exists(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_verification_backlog_warning",
                "sequence": 2,
                "queue_depth": 1000,
                "queue_capacity": 1000,
            },
            {
                "event_type": "qa_decision_verification_skipped",
                "sequence": 3,
                "governance_record_hash": "sha256:" + "e" * 64,
                "reason": "verification_queue_overflow",
            },
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["modes"]["post_hoc"]["status"] == "behind"
    assert payload["modes"]["post_hoc"]["queue_depth"] == 1000
    assert payload["modes"]["post_hoc"]["skipped"] == 1


def test_conformance_mode3_learning_and_attention(tmp_path):
    learning_chain = tmp_path / "qa-learning.jsonl"
    _write_records(
        learning_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_spc_finding",
                "sequence": 2,
                "metric_id": "SPC-001",
                "metric_name": "ALLOW rate",
                "decisions_collected": 42,
                "minimum_required": 100,
                "status": "learning",
            },
        ],
    )
    learning = build_conformance_payload(DashboardQAChainReader(learning_chain))
    assert learning["modes"]["spc"]["status"] == "warming_up"
    assert learning["modes"]["spc"]["decisions_collected"] == 42

    attention_chain = tmp_path / "qa-attention.jsonl"
    _write_records(
        attention_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_spc_finding",
                "sequence": 2,
                "metric_id": "SPC-001",
                "metric_name": "ALLOW rate",
                "current_value": 0.97,
                "ucl": 0.82,
                "lcl": 0.38,
                "window": "1h",
                "status": "above_ucl",
            },
        ],
    )
    attention = build_conformance_payload(DashboardQAChainReader(attention_chain))
    assert attention["state"] == "attention"
    assert attention["modes"]["spc"]["status"] == "attention"
    assert attention["modes"]["spc"]["metric_id"] == "SPC-001"


def test_python_reads_rust_mode2_mode3_record_shapes(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            {
                "event_type": "qa_decision_verification",
                "sequence": 2,
                "governance_record_hash": "sha256:" + "f" * 64,
                "decision_type": "DENY",
                "tool_name": "Bash",
                "checks_performed": {
                    "structural_integrity": "pass",
                    "classification_consistency": "pass",
                    "approval_provenance": "pass",
                    "negative_constraints": "pass",
                    "behavioral_baseline": "pass",
                },
                "all_clear": True,
                "findings": [],
            },
            {
                "event_type": "qa_spc_finding",
                "sequence": 3,
                "metric_id": "SPC-005",
                "metric_name": "Decision throughput",
                "current_value": 101.0,
                "ucl": 100.0,
                "lcl": 100.0,
                "window": "aggregate",
                "status": "above_ucl",
            },
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["modes"]["post_hoc"]["status"] == "active"
    assert payload["modes"]["spc"]["status"] == "attention"


def _snapshot(sequence):
    return {
        "event_type": "qa_environmental_snapshot",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "policy_rules_hash": "sha256:" + "a" * 64,
        "capability_registry_hash": "sha256:" + "b" * 64,
        "checks": {"ENV-001": {"status": "pass"}},
        "active_conditions": [],
        "overall": "healthy",
    }


def _write_records(path, records):
    path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )
