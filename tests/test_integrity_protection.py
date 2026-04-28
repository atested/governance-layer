import json
import sys
from pathlib import Path
from typing import Optional

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "proxy", REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from integrity_monitor import IntegrityMonitor, IntegrityViolation
from proxy.server import ChainRecorder, mediate_decision, record_startup_integrity_events


def _record(label: str) -> dict:
    return {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-04-26T00:00:00Z",
        "request_id": label,
        "session_id": "",
        "user_identity": "",
        "original_tool": "Read",
        "classification": {
            "action_type": "read",
            "targets": [],
            "scope": "unknown",
            "confidence_tier": 1,
        },
        "evidence": {},
        "policy_decision": "ALLOW",
        "policy_reasons": [],
        "matched_rule": "test",
        "prev_record_hash": None,
        "record_hash": None,
    }


def _monitor(tmp_path: Path, chain_path: Path, policy_path: Optional[Path] = None) -> IntegrityMonitor:
    policy = policy_path or tmp_path / "policy-rules.json"
    if not policy.exists():
        policy.write_text('{"rules":[]}\n', encoding="utf-8")
    code_file = tmp_path / "server.py"
    code_file.write_text("print('proxy')\n", encoding="utf-8")
    return IntegrityMonitor(
        chain_path,
        metadata_path=tmp_path / "chain.integrity.json",
        policy_path=policy,
        repo_root=tmp_path,
        code_paths=[code_file],
    )


def test_missing_chain_detected_after_previous_run(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    monitor = _monitor(tmp_path, chain_path)
    monitor.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
    recorder.append_atomic(_record("one"))

    chain_path.unlink()

    restarted = _monitor(tmp_path, chain_path)
    with pytest.raises(IntegrityViolation, match="chain file missing"):
        restarted.verify_startup_chain()


def test_truncated_chain_detected_at_startup(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    monitor = _monitor(tmp_path, chain_path)
    monitor.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
    recorder.append_atomic(_record("one"))
    recorder.append_atomic(_record("two"))

    first_line = chain_path.read_text(encoding="utf-8").splitlines()[0]
    chain_path.write_text(first_line + "\n", encoding="utf-8")

    restarted = _monitor(tmp_path, chain_path)
    with pytest.raises(IntegrityViolation, match="chain truncated"):
        restarted.verify_startup_chain()


def test_runtime_chain_deletion_blocks_next_append(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    monitor = _monitor(tmp_path, chain_path)
    monitor.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
    recorder.append_atomic(_record("one"))

    chain_path.unlink()

    with pytest.raises(IntegrityViolation, match="chain integrity violation"):
        recorder.append_atomic(_record("two"))
    side_events = (tmp_path / "chain.integrity.events.jsonl").read_text(encoding="utf-8")
    assert "chain_file_missing" in side_events


def test_policy_rules_change_records_event_and_denies(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    policy_path = tmp_path / "policy-rules.json"
    policy_path.write_text('{"rules":[],"default_decision":"ALLOW"}\n', encoding="utf-8")
    monitor = _monitor(tmp_path, chain_path, policy_path)
    monitor.verify_startup_chain()
    monitor.startup_hashes()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

    policy_path.write_text('{"rules":[],"default_decision":"DENY"}\n', encoding="utf-8")
    record = mediate_decision(
        "Read",
        {"file_path": str(tmp_path / "README.md")},
        policy={"rules": [], "default_decision": "ALLOW"},
        chain_recorder=recorder,
        integrity_monitor=monitor,
    )

    assert record["policy_decision"] == "DENY"
    assert record["matched_rule"] == "integrity_policy_rules_changed"
    rows = [
        json.loads(line)
        for line in chain_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["event_type"] == "policy_rules_changed"
    assert rows[1]["record_type"] == "mediated_decision"


def test_proxy_code_hash_recorded_on_startup(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    monitor = _monitor(tmp_path, chain_path)
    monitor.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

    hashes = record_startup_integrity_events(
        recorder,
        monitor,
        user_identity="operator@example.com",
        session_id="startup-test",
    )

    rows = [
        json.loads(line)
        for line in chain_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_types = [row["event_type"] for row in rows]
    assert "proxy_startup_code_hash" in event_types
    assert "policy_rules_loaded" in event_types
    startup = next(row for row in rows if row["event_type"] == "proxy_startup_code_hash")
    assert startup["current_proxy_code_hash"] == hashes["current_proxy_code_hash"]
    assert startup["user_identity"] == "operator@example.com"


def test_proxy_code_hash_change_recorded_on_restart(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    code_file = tmp_path / "server.py"
    code_file.write_text("print('one')\n", encoding="utf-8")
    policy_path = tmp_path / "policy-rules.json"
    policy_path.write_text('{"rules":[]}\n', encoding="utf-8")

    monitor = IntegrityMonitor(
        chain_path,
        metadata_path=tmp_path / "chain.integrity.json",
        policy_path=policy_path,
        repo_root=tmp_path,
        code_paths=[code_file],
    )
    monitor.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
    first = record_startup_integrity_events(recorder, monitor)

    code_file.write_text("print('two')\n", encoding="utf-8")
    restarted = IntegrityMonitor(
        chain_path,
        metadata_path=tmp_path / "chain.integrity.json",
        policy_path=policy_path,
        repo_root=tmp_path,
        code_paths=[code_file],
    )
    restarted.verify_startup_chain()
    recorder = ChainRecorder(chain_path, integrity_monitor=restarted)
    second = record_startup_integrity_events(recorder, restarted)

    rows = [
        json.loads(line)
        for line in chain_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    changed = [row for row in rows if row["event_type"] == "proxy_code_hash_changed"]
    assert len(changed) == 1
    assert changed[0]["previous_proxy_code_hash"] == first["current_proxy_code_hash"]
    assert changed[0]["current_proxy_code_hash"] == second["current_proxy_code_hash"]
