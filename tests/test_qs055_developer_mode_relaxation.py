"""QS-055 #1 — developer mode relaxes QA integrity checks.

In developer mode the proxy must FORWARD operations past two classes of QA gate
failure — active conditions and QA chain staleness — annotating every resulting
record with developer_mode_qa_relaxation instead of blocking. Hash mismatch and
an absent QA chain still block even in developer mode, and production mode never
relaxes anything.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "proxy", REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import proxy.server as server
from proxy.server import (
    ChainRecorder,
    compute_capability_registry_hash,
    mediate_decision,
)
from proxy.qa_gate import QAChainTailReader, ProxyQualityGate
from policy_eval_v2 import compute_policy_rules_hash
from qa_chain_fixtures import write_fixture


POLICY = {"rules": [], "default_decision": "ALLOW", "default_reason": "test allow"}


def _policy_hash():
    return compute_policy_rules_hash(POLICY)


def _gate(path: Path, *, heartbeat_seconds: float = 30.0) -> ProxyQualityGate:
    return ProxyQualityGate(
        QAChainTailReader(path, chunk_size=2048),
        expected_policy_rules_hash=_policy_hash(),
        expected_capability_registry_hash=compute_capability_registry_hash(),
        stale_cycles=1,
        heartbeat_seconds=heartbeat_seconds,
        now=lambda: 1000.0,
    )


def _mediate(tmp_path: Path, fixture: str, *, heartbeat_seconds: float = 30.0):
    qa_path = tmp_path / "qa-chain.jsonl"
    chain_path = tmp_path / "decision-chain.jsonl"
    write_fixture(
        qa_path,
        fixture,
        policy_rules_hash=_policy_hash(),
        capability_registry_hash=compute_capability_registry_hash(),
    )
    gate = _gate(qa_path, heartbeat_seconds=heartbeat_seconds)
    if fixture == "stale":
        assert gate.check().ok  # prime _last_sequence so the next check goes stale
    recorder = ChainRecorder(chain_path)
    record = mediate_decision(
        "Bash", {"command": "echo hello"},
        policy=POLICY, chain_recorder=recorder, qa_gate=gate,
    )
    rows = []
    if chain_path.exists():
        rows = [json.loads(l) for l in chain_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return record, rows


@pytest.fixture
def developer_mode(monkeypatch):
    monkeypatch.setattr(server, "developer_mode_active", lambda: True)


def test_developer_mode_forwards_active_condition(tmp_path, developer_mode):
    record, rows = _mediate(tmp_path, "condition")
    # Forwarded, not blocked: a real mediated decision, not an integrity error.
    assert record.get("event_type") != "governance_integrity_error"
    assert record["record_type"] == "mediated_decision"
    assert record["policy_decision"] == "ALLOW"
    assert record["developer_mode"] is True
    relax = record["developer_mode_qa_relaxation"]
    assert relax["condition_source"] == "active_condition"
    assert relax["condition_detail"]
    # The annotation is persisted on the chain record too.
    assert rows[-1]["developer_mode_qa_relaxation"]["condition_source"] == "active_condition"


def test_developer_mode_forwards_qa_chain_staleness(tmp_path, developer_mode):
    record, _rows = _mediate(tmp_path, "stale", heartbeat_seconds=0.0)
    assert record.get("event_type") != "governance_integrity_error"
    assert record["record_type"] == "mediated_decision"
    assert record["policy_decision"] == "ALLOW"
    assert record["developer_mode_qa_relaxation"]["condition_source"] == "qa_chain_staleness"


def test_developer_mode_still_blocks_hash_mismatch(tmp_path, developer_mode):
    record, rows = _mediate(tmp_path, "hash_mismatch")
    # Hash mismatch means the governance config can't be trusted — block anyway.
    assert record["event_type"] == "governance_integrity_error"
    assert record["policy_decision"] == "INTEGRITY_ERROR"
    assert rows[-1]["event_type"] == "governance_integrity_error"


def test_developer_mode_still_blocks_absent_qa_chain(tmp_path, developer_mode):
    record, _rows = _mediate(tmp_path, "absent")
    assert record["event_type"] == "governance_integrity_error"


def test_production_mode_blocks_active_condition(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "developer_mode_active", lambda: False)
    record, rows = _mediate(tmp_path, "condition")
    assert record["event_type"] == "governance_integrity_error"
    assert record["condition_source"] == "active_condition"
    assert "developer_mode_qa_relaxation" not in record
