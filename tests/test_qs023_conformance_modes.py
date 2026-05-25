import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard"))

from conformance import DashboardQAChainReader, build_conformance_payload


def test_conformance_returns_all_five_modes_active(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            _decision_verification(2),
            _spc_status(3, status="active"),
            _element_verification(4, flagged=0),
            _behavioral_analysis(5, anomaly_count=0),
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "verified"
    assert payload["modes"]["environmental"]["status"] == "healthy"
    assert payload["modes"]["post_hoc"]["status"] == "active"
    assert payload["modes"]["spc"]["status"] == "active"
    assert payload["modes"]["element"]["status"] == "active"
    assert payload["modes"]["behavioral"]["status"] == "active"


def test_conformance_surfaces_behavioral_findings(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            _behavioral_analysis(
                2,
                anomaly_count=1,
                findings=[{
                    "type": "security_relevant_pattern",
                    "subtype": "new_tool_appeared",
                    "detail": "new tool appeared",
                    "severity": "medium",
                }],
            ),
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "attention"
    assert payload["modes"]["behavioral"]["status"] == "finding"
    assert payload["modes"]["behavioral"]["anomaly_count"] == 1
    assert payload["modes"]["behavioral"]["findings"][0]["subtype"] == "new_tool_appeared"


def test_conformance_renders_behavioral_warmup(tmp_path):
    # QS-039 #18: a warm-up behavioral record renders as a distinct
    # "warming_up" mode state with "warming up (N/M decisions)" detail, and
    # does NOT drive the overall conformance state to attention.
    qa_chain = tmp_path / "qa-chain.jsonl"
    warmup = _behavioral_analysis(2, anomaly_count=0)
    warmup["warm_up"] = True
    warmup["decisions_analyzed"] = 12
    warmup["minimum_required"] = 100
    _write_records(qa_chain, [_snapshot(1), warmup])

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "verified"
    behavioral = payload["modes"]["behavioral"]
    assert behavioral["status"] == "warming_up"
    assert behavioral["decisions_analyzed"] == 12
    assert behavioral["minimum_required"] == 100
    assert behavioral["detail"] == "warming up (12/100 decisions)"


def test_conformance_surfaces_element_verification_results(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            _element_verification(
                2,
                flagged=1,
                findings=[{
                    "element_id": "HASH_LINKAGE",
                    "severity": "critical",
                    "detail": "hash linkage broken",
                }],
            ),
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "attention"
    assert payload["modes"]["element"]["status"] == "finding"
    assert payload["modes"]["element"]["elements_flagged"] == 1
    assert payload["modes"]["element"]["findings"][0]["element_id"] == "HASH_LINKAGE"


def test_python_reads_rust_behavioral_and_element_record_shapes(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_records(
        qa_chain,
        [
            _snapshot(1),
            _behavioral_analysis(2, anomaly_count=0),
            _element_verification(3, flagged=0),
        ],
    )

    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["modes"]["behavioral"]["status"] == "active"
    assert payload["modes"]["behavioral"]["latest"]["event_type"] == "qa_behavioral_analysis"
    assert payload["modes"]["element"]["status"] == "active"
    assert payload["modes"]["element"]["latest"]["event_type"] == "qa_element_verification"


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


def _decision_verification(sequence):
    return {
        "event_type": "qa_decision_verification",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "governance_record_hash": "sha256:" + "c" * 64,
        "decision_type": "ALLOW",
        "tool_name": "Read",
        "checks_performed": {"structural_integrity": "pass"},
        "all_clear": True,
        "findings": [],
    }


def _spc_status(sequence, status):
    return {
        "event_type": "qa_spc_finding",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:02Z",
        "metric_id": "SPC-001",
        "metric_name": "ALLOW rate",
        "current_value": 0.5,
        "ucl": 1.0,
        "lcl": 0.0,
        "window": "aggregate",
        "status": status,
        "detail": "SPC monitoring active",
    }


def _element_verification(sequence, flagged, findings=None):
    return {
        "event_type": "qa_element_verification",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:03Z",
        "spec_id": "hand-curated-quality-service-v1",
        "elements_checked": 6,
        "elements_passed": 6 - flagged,
        "elements_flagged": flagged,
        "elements_skipped": 0,
        "findings": findings or [],
        "coverage": {"active_verified": 6 - flagged},
    }


def _behavioral_analysis(sequence, anomaly_count, findings=None):
    return {
        "event_type": "qa_behavioral_analysis",
        "sequence": sequence,
        "timestamp_utc": "2026-05-23T14:30:04Z",
        "analysis_window": "1h",
        "findings": findings or [],
        "anomaly_count": anomaly_count,
    }


def _write_records(path, records):
    path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )
