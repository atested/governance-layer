"""Contract tests for SCH-GOV-001's fail-closed decision-chain writer."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

Ed25519PrivateKey = pytest.importorskip(
    "cryptography.hazmat.primitives.asymmetric.ed25519"
).Ed25519PrivateKey


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from governance_chain import (  # noqa: E402
    GovernanceChainError,
    GovernanceChainRecorder,
    validate_record,
    verify_signature,
)


def test_production_record_is_hash_linked_and_ed25519_signed(tmp_path):
    key = Ed25519PrivateKey.generate()
    recorder = GovernanceChainRecorder(tmp_path / "chain.jsonl", production=True, signing_key=key)
    first = recorder.append_mediated_decision(subject_id="operator-1", payload={"decision": "ALLOW"})
    second = recorder.append_mediated_decision(subject_id="operator-1", payload={"decision": "DENY"})

    assert first["prev_record_hash"] is None
    assert second["prev_record_hash"] == first["record_hash"]
    validate_record(second, require_signature=True)
    verify_signature(second, key.public_key())


def test_tampered_chain_fails_closed_before_append(tmp_path):
    path = tmp_path / "chain.jsonl"
    recorder = GovernanceChainRecorder(path)
    recorder.append_mediated_decision(subject_id="operator-1", payload={"decision": "ALLOW"})
    path.write_text(path.read_text(encoding="utf-8").replace("ALLOW", "DENY"), encoding="utf-8")

    with pytest.raises(GovernanceChainError, match="record_hash mismatch"):
        recorder.append_mediated_decision(subject_id="operator-1", payload={"decision": "ALLOW"})


def test_concurrent_writers_advance_one_head_at_a_time(tmp_path):
    path = tmp_path / "chain.jsonl"
    errors = []

    def append(index):
        try:
            GovernanceChainRecorder(path).append_mediated_decision(
                subject_id=f"operator-{index}", payload={"decision": "ALLOW"}
            )
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=append, args=(i,)) for i in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    import json
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 12
    for index, record in enumerate(records):
        assert record["prev_record_hash"] == (None if index == 0 else records[index - 1]["record_hash"])
