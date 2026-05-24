"""Tests for scripts/verify-cross-chain.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))


def _load_linker():
    spec = importlib.util.spec_from_file_location(
        "verify_cross_chain_mod", SCRIPTS / "verify-cross-chain.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LINKER = _load_linker()


def _gov_decision(record_hash: str, decision: str, tool: str = "Bash") -> dict:
    return {
        "record_type": "mediated_decision",
        "record_version": "2.0",
        "policy_decision": decision,
        "tool": tool,
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "record_hash": record_hash,
    }


def _gov_integrity_error(record_hash: str, source: str = "qa_chain_staleness") -> dict:
    return {
        "event_type": "governance_integrity_error",
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "tool_name": "Bash",
        "condition_source": source,
        "condition_detail": "fixture",
        "action_taken": "integrity_error_returned",
        "policy_decision": "INTEGRITY_ERROR",
        "record_hash": record_hash,
    }


def _qa_verification(governance_hash: str, decision: str = "ALLOW") -> dict:
    return {
        "event_type": "qa_decision_verification",
        "sequence": 1,
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "governance_record_hash": governance_hash,
        "decision_type": decision,
        "tool_name": "Bash",
        "checks_performed": {"structural_integrity": "pass"},
        "all_clear": True,
    }


def _qa_skipped(governance_hash: str) -> dict:
    return {
        "event_type": "qa_decision_verification_skipped",
        "sequence": 1,
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "governance_record_hash": governance_hash,
        "reason": "verification_queue_overflow",
    }


def _qa_condition(governance_ref: str) -> dict:
    return {
        "event_type": "qa_condition_detected",
        "sequence": 1,
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "condition_id": "CR-CRIT-001",
        "condition_type": "stale_rules",
        "severity": "critical",
        "detail": "fixture",
        "governance_record_ref": governance_ref,
    }


def _qa_snapshot_with_condition(condition_id: str) -> dict:
    return {
        "event_type": "qa_environmental_snapshot",
        "sequence": 1,
        "timestamp_utc": "2026-05-23T14:30:01Z",
        "policy_rules_hash": "sha256:" + "a" * 64,
        "capability_registry_hash": "sha256:" + "b" * 64,
        "checks": {},
        "active_conditions": [condition_id],
        "overall": "intervention",
    }


def _write_chain(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")


def _hash(i: int) -> str:
    return "sha256:" + str(i).zfill(64)


# ---------------------------------------------------------------------------
# 100% coverage
# ---------------------------------------------------------------------------


def test_full_coverage(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(
        gov_chain,
        [_gov_decision(_hash(1), "ALLOW"), _gov_decision(_hash(2), "DENY")],
    )
    _write_chain(
        qa_chain,
        [_qa_verification(_hash(1), "ALLOW"), _qa_verification(_hash(2), "DENY")],
    )
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["governance_decisions"] == 2
    assert report["decisions_verified"] == 2
    assert report["decisions_skipped_honestly"] == 0
    assert report["decisions_unverified_gap"] == 0
    assert report["coverage_percent"] == 100.0
    assert report["unverified_decisions_sample"] == []


# ---------------------------------------------------------------------------
# Unverified gap
# ---------------------------------------------------------------------------


def test_unverified_gap(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(
        gov_chain,
        [
            _gov_decision(_hash(1), "ALLOW"),
            _gov_decision(_hash(2), "ALLOW"),  # no QA verification for this one
        ],
    )
    _write_chain(qa_chain, [_qa_verification(_hash(1), "ALLOW")])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["governance_decisions"] == 2
    assert report["decisions_verified"] == 1
    assert report["decisions_skipped_honestly"] == 0
    assert report["decisions_unverified_gap"] == 1
    assert report["coverage_percent"] == 50.0
    assert len(report["unverified_decisions_sample"]) == 1
    assert report["unverified_decisions_sample"][0]["record_hash"] == _hash(2)


# ---------------------------------------------------------------------------
# Honest skip
# ---------------------------------------------------------------------------


def test_honest_skip_counts_as_covered(tmp_path):
    """Skipped is documented gap; counts toward coverage."""
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(
        gov_chain,
        [
            _gov_decision(_hash(1), "ALLOW"),
            _gov_decision(_hash(2), "ALLOW"),
        ],
    )
    _write_chain(
        qa_chain,
        [_qa_verification(_hash(1), "ALLOW"), _qa_skipped(_hash(2))],
    )
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["decisions_verified"] == 1
    assert report["decisions_skipped_honestly"] == 1
    assert report["decisions_unverified_gap"] == 0
    assert report["coverage_percent"] == 100.0


def test_distinguish_skip_from_gap(tmp_path):
    """Output must distinguish 'not verified' from 'verification skipped'."""
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(
        gov_chain,
        [
            _gov_decision(_hash(1), "ALLOW"),  # gap
            _gov_decision(_hash(2), "ALLOW"),  # skipped
        ],
    )
    _write_chain(qa_chain, [_qa_skipped(_hash(2))])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["decisions_unverified_gap"] == 1
    assert report["decisions_skipped_honestly"] == 1
    # The two should be reported distinctly, not collapsed.
    assert report["decisions_verified"] != report["decisions_skipped_honestly"]


# ---------------------------------------------------------------------------
# Integrity errors
# ---------------------------------------------------------------------------


def test_integrity_error_with_snapshot_evidence(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(
        gov_chain,
        [_gov_integrity_error(_hash(99), source="hash_mismatch")],
    )
    _write_chain(qa_chain, [_qa_snapshot_with_condition("CR-CRIT-001")])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["governance_integrity_errors"] == 1
    assert report["integrity_errors_with_evidence"] == 1
    assert report["integrity_errors_without_evidence"] == 0


def test_integrity_error_staleness_is_self_evident(tmp_path):
    """A staleness error doesn't need a qa_condition_detected to be explained —
    the absence of a recent snapshot IS the evidence."""
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_integrity_error(_hash(99), source="qa_chain_staleness")])
    _write_chain(qa_chain, [])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["integrity_errors_with_evidence"] == 1
    assert report["integrity_errors_without_evidence"] == 0


def test_integrity_error_without_evidence(tmp_path):
    """active_condition source but QA chain has no matching condition or snapshot."""
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_integrity_error(_hash(99), source="active_condition")])
    _write_chain(qa_chain, [])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["integrity_errors_with_evidence"] == 0
    assert report["integrity_errors_without_evidence"] == 1


# ---------------------------------------------------------------------------
# Chain length edge cases
# ---------------------------------------------------------------------------


def test_governance_chain_absent(tmp_path):
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(qa_chain, [])
    rc = LINKER.main([str(tmp_path / "missing.jsonl"), str(qa_chain)])
    assert rc == 2


def test_qa_chain_absent_with_decisions(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    _write_chain(gov_chain, [_gov_decision(_hash(1), "ALLOW")])
    rc = LINKER.main([str(gov_chain), str(tmp_path / "missing-qa.jsonl")])
    assert rc == 2


def test_empty_governance_chain(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [])
    _write_chain(qa_chain, [])
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["governance_decisions"] == 0
    assert report["decisions_unverified_gap"] == 0
    assert report["coverage_percent"] == 100.0


def test_different_length_chains(tmp_path):
    """QA chain has extra records beyond what governance chain has."""
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_decision(_hash(1), "ALLOW")])
    _write_chain(
        qa_chain,
        [
            _qa_verification(_hash(1)),
            _qa_snapshot_with_condition("CR-MED-001"),
            _qa_snapshot_with_condition("CR-MED-001"),
        ],
    )
    report = LINKER.link_chains(gov_chain, qa_chain)
    assert report["decisions_verified"] == 1
    assert report["coverage_percent"] == 100.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_full_coverage_exit_zero(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_decision(_hash(1), "ALLOW")])
    _write_chain(qa_chain, [_qa_verification(_hash(1))])
    rc = LINKER.main([str(gov_chain), str(qa_chain)])
    assert rc == 0


def test_cli_gap_exit_one(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_decision(_hash(1), "ALLOW"), _gov_decision(_hash(2), "ALLOW")])
    _write_chain(qa_chain, [_qa_verification(_hash(1))])
    rc = LINKER.main([str(gov_chain), str(qa_chain)])
    assert rc == 1


def test_cli_summary_json(tmp_path):
    gov_chain = tmp_path / "decision-chain.jsonl"
    qa_chain = tmp_path / "qa-chain.jsonl"
    _write_chain(gov_chain, [_gov_decision(_hash(1), "ALLOW")])
    _write_chain(qa_chain, [_qa_verification(_hash(1))])
    summary_path = tmp_path / "summary.json"
    rc = LINKER.main([str(gov_chain), str(qa_chain), "--summary-json", str(summary_path)])
    assert rc == 0
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["governance_decisions"] == 1
    assert data["coverage_percent"] == 100.0
