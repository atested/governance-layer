"""QS-039 #22: Python QA chain 4KB record-size invariant.

Parity with the Rust writer (quality-service/src/writer.rs:append_record),
which rejects any QA chain record line over 4096 bytes.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from qa_chain_limits import MAX_QA_RECORD_BYTES, enforce_qa_record_size


def test_limit_matches_rust_writer():
    assert MAX_QA_RECORD_BYTES == 4096


def test_under_limit_passes():
    enforce_qa_record_size("x" * 4096)  # exactly at the limit is allowed


def test_over_limit_raises():
    with pytest.raises(ValueError, match="exceeds 4KB atomic append limit"):
        enforce_qa_record_size("x" * 4097)


def test_over_limit_reports_sequence():
    with pytest.raises(ValueError, match="sequence 7"):
        enforce_qa_record_size("x" * 5000, sequence=7)


def test_write_qa_chain_rejects_oversized_record(tmp_path):
    """The Python QA-chain writer refuses to emit an oversized record."""
    sys.path.insert(0, str(REPO / "scripts"))
    from qa_chain_fixtures import write_qa_chain

    # A record whose canonical JSON is well over 4KB (a giant detail field).
    oversized = {
        "event_type": "qa_environmental_snapshot",
        "sequence": 1,
        "detail": "z" * 5000,
    }
    with pytest.raises(ValueError, match="exceeds 4KB atomic append limit"):
        write_qa_chain(tmp_path / "qa-chain.jsonl", [oversized])
