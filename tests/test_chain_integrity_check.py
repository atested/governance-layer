"""Tests for pre-append chain integrity verification.

Verifies that ChainRecorder._last_hash() detects tampered tail records
by recomputing the hash and comparing to the stored value.
"""

import json
import logging
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "proxy"))
sys.path.insert(0, str(REPO / "scripts"))

from policy_eval_v2 import _compute_record_hash
from proxy.server import ChainRecorder


def _make_chain(tmpdir, records):
    """Write records to a chain file and return the path."""
    chain_path = Path(tmpdir) / "test_chain.jsonl"
    with open(chain_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return chain_path


def _make_valid_record(prev_hash=None, **extra):
    """Create a record with a valid computed hash."""
    record = {
        "event_type": "test",
        "prev_record_hash": prev_hash,
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
        **extra,
    }
    record["record_hash"] = _compute_record_hash(record)
    return record


class TestChainIntegrityCheck:
    def test_empty_chain_returns_none(self):
        """Empty chain file → None hash."""
        tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
        chain_path = Path(tmpdir) / "chain.jsonl"
        chain_path.touch()
        recorder = ChainRecorder(chain_path)
        assert recorder._last_hash() is None

    def test_missing_chain_returns_none(self):
        """Non-existent chain file → None hash."""
        tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
        recorder = ChainRecorder(Path(tmpdir) / "missing.jsonl")
        assert recorder._last_hash() is None

    def test_valid_tail_returns_hash(self):
        """Valid tail record → returns its hash without warnings."""
        tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
        record = _make_valid_record()
        chain_path = _make_chain(tmpdir, [record])
        recorder = ChainRecorder(chain_path)
        assert recorder._last_hash() == record["record_hash"]

    def test_tampered_tail_logs_error(self, caplog):
        """Tampered tail record → logs integrity error, still returns hash."""
        tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
        record = _make_valid_record()
        original_hash = record["record_hash"]

        # Tamper: modify a field after hashing
        record["event_type"] = "tampered"
        # record_hash is now stale (doesn't match recomputed)

        chain_path = _make_chain(tmpdir, [record])
        recorder = ChainRecorder(chain_path)

        with caplog.at_level(logging.ERROR, logger="proxy.server"):
            result = recorder._last_hash()

        # Should still return the stored hash (for chain continuity)
        assert result == original_hash
        # But should have logged the integrity error
        assert any("CHAIN INTEGRITY" in msg for msg in caplog.messages), (
            "Tampered tail should log CHAIN INTEGRITY error"
        )

    def test_multi_record_checks_only_tail(self):
        """Only the tail record is verified, not the entire chain."""
        tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
        r1 = _make_valid_record()
        r2 = _make_valid_record(prev_hash=r1["record_hash"], data="second")
        chain_path = _make_chain(tmpdir, [r1, r2])
        recorder = ChainRecorder(chain_path)
        assert recorder._last_hash() == r2["record_hash"]
