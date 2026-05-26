import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from event_model import validate_non_action_event
from policy_eval_v2 import compute_policy_rules_hash
from proxy.qa_gate import QAChainTailReader, ProxyQualityGate
from proxy.server import (
    ChainRecorder,
    compute_capability_registry_hash,
    mediate_decision,
)
from proxy import server as proxy_server
from qa_chain_fixtures import write_fixture, write_large_fixture


POLICY = {
    "rules": [],
    "default_decision": "ALLOW",
    "default_reason": "test allow",
}


def _policy_hash():
    return compute_policy_rules_hash(POLICY)


def _cap_hash():
    return compute_capability_registry_hash()


def _gate(path: Path, *, heartbeat_seconds: float = 30.0) -> ProxyQualityGate:
    return ProxyQualityGate(
        QAChainTailReader(path, chunk_size=2048),
        expected_policy_rules_hash=_policy_hash(),
        expected_capability_registry_hash=_cap_hash(),
        stale_cycles=1,
        heartbeat_seconds=heartbeat_seconds,
        now=lambda: 1000.0,
    )


def _mediate_with_fixture(tmp_path: Path, fixture: str, *, heartbeat_seconds: float = 30.0):
    qa_path = tmp_path / "qa-chain.jsonl"
    chain_path = tmp_path / "decision-chain.jsonl"
    write_fixture(
        qa_path,
        fixture,
        policy_rules_hash=_policy_hash(),
        capability_registry_hash=_cap_hash(),
    )
    gate = _gate(qa_path, heartbeat_seconds=heartbeat_seconds)
    if fixture == "stale":
        first = gate.check()
        assert first.ok

    cap_registry = tmp_path / "capability-registry.json"
    cap_registry.write_text(
        json.dumps({
            "version": "0.1",
            "governance_posture": {"mode": "production"},
            "tools": [],
        }),
        encoding="utf-8",
    )
    recorder = ChainRecorder(chain_path)
    with patch.object(proxy_server, "CAP_REGISTRY_PATH", cap_registry):
        record = mediate_decision(
            "Bash",
            {"command": "echo hello"},
            policy=POLICY,
            chain_recorder=recorder,
            qa_gate=gate,
        )
    rows = []
    if chain_path.exists():
        rows = [json.loads(line) for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return record, rows, chain_path


def _assert_integrity_error(rows, expected_source: str):
    assert rows, "governance chain should contain governance_integrity_error"
    event = rows[-1]
    assert event["event_type"] == "governance_integrity_error"
    assert event["condition_source"] == expected_source
    assert event["policy_decision"] == "INTEGRITY_ERROR"
    ok, err = validate_non_action_event(event)
    assert ok, err
    return event


def test_proxy_proceeds_with_healthy_qa_fixture(tmp_path):
    record, rows, _chain_path = _mediate_with_fixture(tmp_path, "healthy")

    assert record["record_type"] == "mediated_decision"
    assert record["policy_decision"] == "ALLOW"
    assert rows[-1]["record_type"] == "mediated_decision"


def test_proxy_integrity_error_with_stale_qa_fixture(tmp_path):
    record, rows, chain_path = _mediate_with_fixture(tmp_path, "stale", heartbeat_seconds=0.0)

    assert record["event_type"] == "governance_integrity_error"
    _assert_integrity_error(rows, "qa_chain_staleness")
    _assert_verify_chain_passes(chain_path)


def test_proxy_integrity_error_with_condition_fixture(tmp_path):
    record, rows, chain_path = _mediate_with_fixture(tmp_path, "condition")

    assert record["event_type"] == "governance_integrity_error"
    _assert_integrity_error(rows, "active_condition")
    _assert_verify_chain_passes(chain_path)


def test_proxy_integrity_error_with_hash_mismatch_fixture(tmp_path):
    record, rows, chain_path = _mediate_with_fixture(tmp_path, "hash_mismatch")

    assert record["event_type"] == "governance_integrity_error"
    _assert_integrity_error(rows, "hash_mismatch")
    _assert_verify_chain_passes(chain_path)


def test_proxy_integrity_error_with_empty_qa_fixture(tmp_path):
    record, rows, chain_path = _mediate_with_fixture(tmp_path, "empty")

    assert record["event_type"] == "governance_integrity_error"
    _assert_integrity_error(rows, "qa_chain_absent")
    _assert_verify_chain_passes(chain_path)


def test_proxy_integrity_error_with_absent_qa_fixture(tmp_path):
    record, rows, chain_path = _mediate_with_fixture(tmp_path, "absent")

    assert record["event_type"] == "governance_integrity_error"
    _assert_integrity_error(rows, "qa_chain_absent")
    _assert_verify_chain_passes(chain_path)


def test_tail_reader_uses_cached_offset_for_large_chain(tmp_path):
    qa_path = tmp_path / "qa-chain-large.jsonl"
    write_large_fixture(
        qa_path,
        count=10_000,
        policy_rules_hash=_policy_hash(),
        capability_registry_hash=_cap_hash(),
    )
    reader = QAChainTailReader(qa_path, chunk_size=4096)

    first = reader.latest_snapshot()
    assert first.status == "ok"
    assert first.snapshot["sequence"] == 10_000
    assert first.bytes_read < qa_path.stat().st_size

    second = reader.latest_snapshot()
    assert second.status == "ok"
    assert second.snapshot["sequence"] == 10_000
    assert second.bytes_read == 0


def _assert_verify_chain_passes(chain_path: Path):
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "verify-chain.py"), str(chain_path)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
