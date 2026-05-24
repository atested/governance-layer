"""Gate 1B — Chain recorder and integrity monitor tests.

Dispatch: 172-D-2026-0430 (RELEASE-G1B-CHAIN-INTEGRITY-TESTS)

Closes trust-surface test gaps for the chain recorder and integrity
monitor (gaps G-06, G-07, G-08, G-09, G-13).

Scope items:
  1. Malformed records in chain verification
  2. Mixed-chain verification depth
  3. Concurrent appends (INV-010)
  4. Sidecar event triggers (G-06)
  5. chain_integrity_violation chain event (G-07)
  6. Metadata tampering vs. deletion (G-09)
  7. Runtime integrity re-check after policy change
  8. INV-008 replay outcome verification (G-13)
"""

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "proxy", REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from integrity_monitor import (
    IntegrityMonitor,
    IntegrityViolation,
    _metadata_hash,
    _record_hash_for_integrity,
    _canonical,
)
from proxy.server import ChainRecorder, mediate_decision, record_startup_integrity_events


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _record(label: str) -> dict:
    """Build a minimal v2 decision record for testing."""
    return {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-04-30T00:00:00Z",
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
    """Create an IntegrityMonitor with test paths."""
    policy = policy_path or tmp_path / "policy-rules.json"
    if not policy.exists():
        policy.write_text('{"rules":[]}\n', encoding="utf-8")
    code_file = tmp_path / "server.py"
    if not code_file.exists():
        code_file.write_text("print('proxy')\n", encoding="utf-8")
    return IntegrityMonitor(
        chain_path,
        metadata_path=tmp_path / "chain.integrity.json",
        policy_path=policy,
        repo_root=tmp_path,
        code_paths=[code_file],
    )


def _read_chain(chain_path: Path) -> list[dict]:
    """Read all records from a chain JSONL file."""
    if not chain_path.exists():
        return []
    records = []
    for line in chain_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _read_sidecar_events(events_path: Path) -> list[dict]:
    """Read all sidecar events from an events JSONL file."""
    if not events_path.exists():
        return []
    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _compute_record_hash(record: dict) -> str:
    """Compute SHA-256 hash of a record with hash/signature fields nulled."""
    hashable = dict(record)
    hashable["record_hash"] = None
    if "signature" in hashable:
        hashable["signature"] = None
    if "signing_key_id" in hashable:
        hashable["signing_key_id"] = None
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ===========================================================================
# SCOPE 1 — Malformed records in chain verification
# ===========================================================================

class TestMalformedRecords:
    """Verify that chain verification detects and reports malformed
    records rather than silently skipping or crashing.
    """

    def test_corrupt_json_line_detected(self, tmp_path):
        """A line with invalid JSON raises IntegrityViolation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("valid"))

        # Inject corrupt JSON after valid record
        with chain_path.open("a", encoding="utf-8") as f:
            f.write("{corrupt json missing closing\n")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="invalid JSON"):
            restarted.summarize_chain()

    def test_missing_record_hash_field_detected(self, tmp_path):
        """A record missing record_hash raises IntegrityViolation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("valid"))

        # Read valid record, remove record_hash, re-inject
        records = _read_chain(chain_path)
        bad_record = dict(records[0])
        bad_record["record_hash"] = None  # Missing hash
        bad_record["prev_record_hash"] = records[0]["record_hash"]
        with chain_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(bad_record, sort_keys=True, separators=(",", ":")) + "\n")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="record_hash missing"):
            restarted.summarize_chain()

    def test_truncated_line_detected(self, tmp_path):
        """A truncated JSON line (valid prefix but incomplete) detected."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("valid"))

        # Append a truncated JSON line
        with chain_path.open("a", encoding="utf-8") as f:
            f.write('{"record_version":"2.0","record_type":"mediated_dec\n')

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="invalid JSON"):
            restarted.summarize_chain()

    def test_record_hash_mismatch_detected(self, tmp_path):
        """A record with a tampered record_hash is detected."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("valid"))

        # Read valid record, tamper its record_hash, append as second record
        records = _read_chain(chain_path)
        tampered = dict(_record("tampered"))
        tampered["prev_record_hash"] = records[0]["record_hash"]
        tampered["record_hash"] = "sha256:" + "a" * 64  # wrong hash
        with chain_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="record_hash mismatch"):
            restarted.summarize_chain()


# ===========================================================================
# SCOPE 2 — Mixed-chain verification depth
# ===========================================================================

class TestMixedChainVerification:
    """Verify detection of signing anomalies and record gaps."""

    def test_broken_prev_record_hash_linkage(self, tmp_path):
        """A record with wrong prev_record_hash breaks the chain."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("first"))

        # Append a record with deliberately wrong prev_record_hash
        wrong_link = dict(_record("second"))
        wrong_link["prev_record_hash"] = "sha256:" + "b" * 64  # wrong
        wrong_link["record_hash"] = _compute_record_hash(wrong_link)
        with chain_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(wrong_link, sort_keys=True, separators=(",", ":")) + "\n")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="prev_record_hash mismatch"):
            restarted.summarize_chain()

    def test_chain_with_gap_in_sequence_detected(self, tmp_path):
        """Chain with fewer records than expected triggers count mismatch.

        Record 'gaps' are detected by the integrity monitor through
        count comparison — if the chain has fewer records than expected
        (truncation) or more than expected (unauthorized addition).
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))
        recorder.append_atomic(_record("three"))

        # Tamper metadata to expect 5 records (gap of 2)
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_record_count"] = 5
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="chain truncated"):
            restarted.verify_startup_chain()

    def test_extra_valid_records_rebaseline_stale_metadata(self, tmp_path):
        """More valid records than expected rebaseline stale metadata."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))

        # Tamper metadata to expect only 1 record
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_record_count"] = 1
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        summary = restarted.verify_startup_chain()

        assert summary.record_count == 2
        assert (restarted.load_metadata() or {})["expected_record_count"] == 2


# ===========================================================================
# SCOPE 3 — Concurrent appends (INV-010)
# ===========================================================================

class TestConcurrentAppends:
    """INV-010: Lock protocol prevents corruption under contention.

    Tests the actual lock protocol by spawning multiple threads that
    each attempt to append records simultaneously.
    """

    def test_concurrent_thread_appends_preserve_linkage(self, tmp_path):
        """Multiple threads appending simultaneously — all records intact,
        hash linkage unbroken, no duplicates or losses.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()

        num_threads = 8
        records_per_thread = 5
        errors = []

        def append_records(thread_id):
            try:
                recorder = ChainRecorder(chain_path, integrity_monitor=None)
                for i in range(records_per_thread):
                    recorder.append_atomic(_record(f"t{thread_id}-r{i}"))
            except Exception as exc:
                errors.append((thread_id, exc))

        threads = [
            threading.Thread(target=append_records, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # Verify all records are present
        records = _read_chain(chain_path)
        expected_count = num_threads * records_per_thread
        assert len(records) == expected_count, (
            f"Expected {expected_count} records, got {len(records)}"
        )

        # Verify hash linkage is unbroken
        for i, rec in enumerate(records):
            if i == 0:
                assert rec["prev_record_hash"] is None
            else:
                assert rec["prev_record_hash"] == records[i - 1]["record_hash"], (
                    f"Hash linkage broken at record {i}"
                )

        # Verify no duplicate request_ids
        request_ids = [r["request_id"] for r in records]
        assert len(set(request_ids)) == expected_count, "Duplicate records detected"

    def test_concurrent_appends_with_integrity_monitor(self, tmp_path):
        """Concurrent appends with integrity monitor active — chain
        remains consistent and metadata is correctly updated.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()

        num_threads = 4
        records_per_thread = 3
        errors = []

        def append_records(thread_id):
            try:
                recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
                for i in range(records_per_thread):
                    recorder.append_atomic(_record(f"t{thread_id}-r{i}"))
            except Exception as exc:
                errors.append((thread_id, exc))

        threads = [
            threading.Thread(target=append_records, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        records = _read_chain(chain_path)
        expected_count = num_threads * records_per_thread
        assert len(records) == expected_count

        # Verify chain can be summarized without errors (hash linkage intact)
        summary = monitor.summarize_chain()
        assert summary.record_count == expected_count
        assert summary.last_record_hash == records[-1]["record_hash"]


# ===========================================================================
# SCOPE 4 — Sidecar event triggers (G-06)
# ===========================================================================

class TestSidecarEventTriggers:
    """G-06: Verify each sidecar event is triggered with correct content."""

    def test_sidecar_lagging_valid_chain_rebaselines_on_startup(self, tmp_path):
        """4a: A sidecar behind a valid chain is a stale cache, not tamper."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))

        # Simulate stale metadata: expect 1 but chain has validly advanced to 2.
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_record_count"] = 1
        metadata["expected_last_record_hash"] = "sha256:wrong"
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        summary = restarted.verify_startup_chain()

        assert summary.record_count == 2
        assert (restarted.load_metadata() or {})["expected_record_count"] == 2
        events = _read_sidecar_events(restarted.events_path)
        assert "chain_record_count_mismatch" not in [e["event_type"] for e in events]

    def test_chain_tail_hash_mismatch_sidecar(self, tmp_path):
        """4b: Create valid chain, modify stored tail hash, confirm event."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))

        # Tamper metadata: correct count but wrong tail hash
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        real_hash = metadata["expected_last_record_hash"]
        metadata["expected_last_record_hash"] = "sha256:" + "f" * 64
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="hash differs"):
            restarted.verify_startup_chain()

        events = _read_sidecar_events(restarted.events_path)
        hash_events = [e for e in events if e["event_type"] == "chain_tail_hash_mismatch"]
        assert len(hash_events) >= 1
        evt = hash_events[0]
        assert evt["expected_last_record_hash"] == "sha256:" + "f" * 64
        assert evt["actual_last_record_hash"] == real_hash

    def test_chain_archive_failed_sidecar(self, tmp_path):
        """4c: Trigger archive that fails, confirm sidecar event."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))

        # Make archive directory unwritable to force archive failure
        archive_dir = chain_path.parent / "archive"
        archive_dir.mkdir()
        archive_dir.chmod(0o000)

        # Tamper metadata to trigger integrity violation → _block_chain → archive
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_record_count"] = 99
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        try:
            with pytest.raises(IntegrityViolation):
                recorder2 = ChainRecorder(chain_path, integrity_monitor=restarted)
                restarted.load_metadata()
                restarted.verify_chain_writable()
        finally:
            archive_dir.chmod(0o755)

        events = _read_sidecar_events(restarted.events_path)
        archive_fail = [e for e in events if e["event_type"] == "chain_archive_failed"]
        assert len(archive_fail) >= 1, (
            f"Expected chain_archive_failed event, got: {[e['event_type'] for e in events]}"
        )

    def test_chain_archived_after_integrity_violation_sidecar(self, tmp_path):
        """4d: Trigger integrity violation → archival → terminal sidecar.

        This is a terminal event — the chain is archived and the system
        enters a blocked state.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))

        # Delete chain while monitor expects it
        chain_path.unlink()

        with pytest.raises(IntegrityViolation):
            recorder.append_atomic(_record("three"))

        events = _read_sidecar_events(monitor.events_path)
        event_types = [e["event_type"] for e in events]

        # Should have chain_file_missing event (the reason)
        assert "chain_file_missing" in event_types

        # Should have chain_archived_after_integrity_violation (the terminal event)
        assert "chain_archived_after_integrity_violation" in event_types
        terminal = [e for e in events if e["event_type"] == "chain_archived_after_integrity_violation"]
        assert len(terminal) >= 1
        assert "archive_id" in terminal[0]
        assert terminal[0].get("reason") == "chain_file_missing"

    def test_fresh_chain_after_tamper_archive_accepts_subsequent_writes(self, tmp_path):
        """After a tampered chain is archived, metadata is reset for a fresh chain."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))

        rows = _read_chain(chain_path)
        rows[-1]["policy_decision"] = "DENY"
        chain_path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(IntegrityViolation):
            recorder.append_atomic(_record("tamper-detected"))

        metadata = monitor.load_metadata()
        assert metadata["chain_existed"] is False
        assert metadata["expected_record_count"] == 0
        assert not chain_path.exists()

        for i in range(20):
            recorder.append_atomic(_record(f"fresh-{i}"))

        fresh_rows = _read_chain(chain_path)
        assert len(fresh_rows) == 20
        assert fresh_rows[-1]["policy_decision"] == "ALLOW"
        side_events = _read_sidecar_events(monitor.events_path)
        assert not any(e["event_type"] == "chain_file_missing" for e in side_events)

    def test_valid_forward_progress_rebaselines_stale_sidecar(self, tmp_path):
        """A stale sidecar behind a valid chain is refreshed, not blocked."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))

        # Simulate a legitimate writer that appended under the chain lock but
        # crashed before refreshing the sidecar. The chain itself remains valid.
        stale_count = (monitor.load_metadata() or {})["expected_record_count"]
        blind_recorder = ChainRecorder(chain_path, integrity_monitor=None)
        blind_recorder.append_atomic(_record("two"))
        assert len(_read_chain(chain_path)) == stale_count + 1

        recorder.append_atomic(_record("three"))

        metadata = monitor.load_metadata()
        assert metadata["expected_record_count"] == 3
        assert len(_read_chain(chain_path)) == 3
        side_events = _read_sidecar_events(monitor.events_path)
        assert "chain_record_count_mismatch" not in [e["event_type"] for e in side_events]

    def test_fifty_consecutive_appends_keep_sidecar_in_sync(self, tmp_path):
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        for i in range(50):
            recorder.append_atomic(_record(f"append-{i}"))

        metadata = monitor.load_metadata()
        assert metadata["expected_record_count"] == 50
        assert len(_read_chain(chain_path)) == 50


# ===========================================================================
# SCOPE 5 — chain_integrity_violation chain event (G-07)
# ===========================================================================

class TestChainIntegrityViolationEvent:
    """G-07: Verify chain_integrity_violation event recorded to the
    decision chain (not sidecar) during normal operation.

    The policy_rules_changed event is the primary chain-level integrity
    event that demonstrates integrity violations are recorded in the
    chain itself, not just the sidecar.
    """

    def test_policy_change_no_longer_records_chain_event_from_mediate(self, tmp_path):
        """Runtime policy-change gating is superseded by the QA chain gate."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"default_decision":"ALLOW"}\n', encoding="utf-8")
        monitor = _monitor(tmp_path, chain_path, policy_path)
        monitor.verify_startup_chain()
        monitor.startup_hashes()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Change policy during runtime
        policy_path.write_text('{"rules":[],"default_decision":"DENY"}\n', encoding="utf-8")

        # mediate_decision no longer performs direct policy-change gating.
        result = mediate_decision(
            "Read",
            {"file_path": str(tmp_path / "test.txt")},
            policy={"rules": [], "default_decision": "ALLOW"},
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )

        assert result["policy_decision"] == "ALLOW"

        # Verify the chain contains only the mediated decision.
        records = _read_chain(chain_path)
        event_types = [r.get("event_type") for r in records if "event_type" in r]
        assert "policy_rules_changed" not in event_types
        assert records[-1]["record_type"] == "mediated_decision"

    def test_startup_code_hash_change_recorded_in_chain(self, tmp_path):
        """Code change between restarts records proxy_code_hash_changed
        in the decision chain.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        code_file = tmp_path / "server.py"
        code_file.write_text("print('version_1')\n", encoding="utf-8")
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
        record_startup_integrity_events(recorder, monitor)

        # Change code
        code_file.write_text("print('version_2')\n", encoding="utf-8")
        monitor2 = IntegrityMonitor(
            chain_path,
            metadata_path=tmp_path / "chain.integrity.json",
            policy_path=policy_path,
            repo_root=tmp_path,
            code_paths=[code_file],
        )
        monitor2.verify_startup_chain()
        recorder2 = ChainRecorder(chain_path, integrity_monitor=monitor2)
        record_startup_integrity_events(recorder2, monitor2)

        records = _read_chain(chain_path)
        event_types = [r.get("event_type") for r in records if "event_type" in r]
        assert "proxy_code_hash_changed" in event_types


# ===========================================================================
# SCOPE 6 — Metadata tampering vs. deletion (G-09)
# ===========================================================================

class TestMetadataTampering:
    """G-09: Verify detection of metadata field modifications
    (distinct from deletion, which is covered by existing tests).
    """

    def test_tampered_hash_value_detected(self, tmp_path):
        """6a: Modify expected_last_record_hash in metadata — detected."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))

        # Tamper the hash value BUT recompute metadata_hash correctly
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_last_record_hash"] = "sha256:" + "0" * 64
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="hash differs"):
            restarted.verify_startup_chain()

    def test_tampered_record_count_detected(self, tmp_path):
        """6b: Modify expected_record_count in metadata — detected."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)
        recorder.append_atomic(_record("one"))
        recorder.append_atomic(_record("two"))

        # Set count to 5 (chain only has 2)
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        metadata["expected_record_count"] = 5
        metadata["metadata_hash"] = _metadata_hash(metadata)
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="chain truncated"):
            restarted.verify_startup_chain()

    def test_tampered_policy_rules_hash_detected_and_denies(self, tmp_path):
        """6c: Modify policy_rules_hash in metadata — detection + deny-all.

        When the stored policy hash doesn't match the current policy,
        the integrity monitor blocks all operations with a deny.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"default_decision":"ALLOW"}\n', encoding="utf-8")
        monitor = _monitor(tmp_path, chain_path, policy_path)
        monitor.verify_startup_chain()
        monitor.startup_hashes()

        # Modify the policy file (simulating tampering)
        policy_path.write_text('{"rules":[{"id":"evil","match":{},"decision":"ALLOW"}]}\n', encoding="utf-8")

        # check_policy_rules_unchanged should detect the change
        result = monitor.check_policy_rules_unchanged()
        assert result is not None, "Policy change should be detected"
        assert result["previous_policy_rules_hash"] != result["current_policy_rules_hash"]

        # Verify metadata records the blocked state
        metadata = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        assert metadata["blocked_reason"] == "policy_rules_changed"

    def test_tampered_proxy_code_hash_detected(self, tmp_path):
        """6d: Modify proxy code between startups — detected by hash comparison."""
        chain_path = tmp_path / "decision-chain.jsonl"
        code_file = tmp_path / "server.py"
        code_file.write_text("print('original')\n", encoding="utf-8")
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
        hashes1 = monitor.startup_hashes()
        monitor.commit_startup_hashes()

        # Modify code file (simulating tampering)
        code_file.write_text("print('TAMPERED')\n", encoding="utf-8")

        monitor2 = IntegrityMonitor(
            chain_path,
            metadata_path=tmp_path / "chain.integrity.json",
            policy_path=policy_path,
            repo_root=tmp_path,
            code_paths=[code_file],
        )
        monitor2.verify_startup_chain()
        hashes2 = monitor2.startup_hashes()

        assert hashes2["previous_proxy_code_hash"] == hashes1["current_proxy_code_hash"]
        assert hashes2["current_proxy_code_hash"] != hashes1["current_proxy_code_hash"]

    def test_raw_metadata_hash_tamper_detected(self, tmp_path):
        """Modifying metadata without recomputing metadata_hash is caught.

        The metadata_hash field is a self-authenticating hash of all
        other metadata fields. Tampering without recomputing it causes
        load_metadata() to raise IntegrityViolation.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()

        # Read metadata and tamper a field WITHOUT recomputing metadata_hash
        raw = monitor.metadata_path.read_text(encoding="utf-8")
        metadata = json.loads(raw)
        metadata["expected_record_count"] = 999  # tamper
        # Don't recompute metadata_hash — this should be caught
        monitor.metadata_path.write_text(_canonical(metadata) + "\n", encoding="utf-8")

        restarted = _monitor(tmp_path, chain_path)
        with pytest.raises(IntegrityViolation, match="metadata hash mismatch"):
            restarted.load_metadata()


# ===========================================================================
# SCOPE 7 — Runtime integrity re-check after policy change
# ===========================================================================

class TestRuntimePolicyChangeIntegrity:
    """Verify that integrity checks correctly reflect policy changes."""

    def test_policy_change_no_longer_blocks_mediate_decision(self, tmp_path):
        """Policy file changes are detected by IntegrityMonitor but no longer gate mediation directly."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"default_decision":"ALLOW"}\n', encoding="utf-8")
        monitor = _monitor(tmp_path, chain_path, policy_path)
        monitor.verify_startup_chain()
        monitor.startup_hashes()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # First mediation succeeds (policy unchanged)
        result1 = mediate_decision(
            "Read", {"file_path": str(tmp_path / "test.txt")},
            policy={"rules": [], "default_decision": "ALLOW"},
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )
        assert result1["policy_decision"] == "ALLOW"

        # Change policy
        policy_path.write_text('{"rules":[],"default_decision":"DENY"}\n', encoding="utf-8")

        # Second mediation proceeds; the QA gate is now responsible for hash mismatch gating.
        result2 = mediate_decision(
            "Read", {"file_path": str(tmp_path / "test.txt")},
            policy={"rules": [], "default_decision": "ALLOW"},
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )
        assert result2["policy_decision"] == "ALLOW"

        # Acknowledge the change
        monitor.acknowledge_policy_rules_change(operator="admin")

        # Third mediation should proceed normally again
        result3 = mediate_decision(
            "Read", {"file_path": str(tmp_path / "test.txt")},
            policy={"rules": [], "default_decision": "ALLOW"},
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )
        assert result3["policy_decision"] == "ALLOW"

    def test_repeated_policy_changes_each_detected(self, tmp_path):
        """Each policy change is independently detected."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"v":1}\n', encoding="utf-8")
        monitor = _monitor(tmp_path, chain_path, policy_path)
        monitor.verify_startup_chain()
        monitor.startup_hashes()

        # First change
        policy_path.write_text('{"rules":[],"v":2}\n', encoding="utf-8")
        change1 = monitor.check_policy_rules_unchanged()
        assert change1 is not None

        monitor.acknowledge_policy_rules_change(operator="admin")

        # Second change
        policy_path.write_text('{"rules":[],"v":3}\n', encoding="utf-8")
        change2 = monitor.check_policy_rules_unchanged()
        assert change2 is not None
        assert change2["current_policy_rules_hash"] != change1["current_policy_rules_hash"]

    def test_policy_acknowledge_with_fresh_monitor_preserves_chain_checkpoint(self, tmp_path):
        """Dashboard-style acknowledgement must not reset sidecar counts."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"v":1}\n', encoding="utf-8")
        monitor = _monitor(tmp_path, chain_path, policy_path)
        monitor.verify_startup_chain()
        monitor.startup_hashes()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        recorder.append_atomic(_record("before-policy-change"))
        metadata_before = monitor.load_metadata()
        assert metadata_before["expected_record_count"] == 1

        policy_path.write_text('{"rules":[],"v":2}\n', encoding="utf-8")
        assert monitor.check_policy_rules_unchanged() is not None

        fresh_monitor = _monitor(tmp_path, chain_path, policy_path)
        fresh_monitor.acknowledge_policy_rules_change(operator="dashboard")

        metadata_after = fresh_monitor.load_metadata()
        assert metadata_after["expected_record_count"] == 1
        assert metadata_after["expected_last_record_hash"] == metadata_before["expected_last_record_hash"]
        assert metadata_after["blocked_reason"] is None

    def test_policy_acknowledge_with_fresh_monitor_unblocks_running_proxy_monitor(self, tmp_path):
        """Dashboard acknowledgement metadata is a cross-process resume signal."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"v":1}\n', encoding="utf-8")
        proxy_monitor = _monitor(tmp_path, chain_path, policy_path)
        proxy_monitor.verify_startup_chain()
        proxy_monitor.startup_hashes()

        policy_path.write_text('{"rules":[],"v":2}\n', encoding="utf-8")
        assert proxy_monitor.check_policy_rules_unchanged() is not None

        dashboard_monitor = _monitor(tmp_path, chain_path, policy_path)
        dashboard_monitor.acknowledge_policy_rules_change(operator="dashboard")

        assert proxy_monitor.check_policy_rules_unchanged() is None

    def test_policy_acknowledge_survives_stale_dashboard_chain_refresh(self, tmp_path):
        """A stale dashboard monitor must not restore deny-all after ack event append."""
        chain_path = tmp_path / "decision-chain.jsonl"
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[],"v":1}\n', encoding="utf-8")
        proxy_monitor = _monitor(tmp_path, chain_path, policy_path)
        proxy_monitor.verify_startup_chain()
        proxy_monitor.startup_hashes()

        policy_path.write_text('{"rules":[],"v":2}\n', encoding="utf-8")
        assert proxy_monitor.check_policy_rules_unchanged() is not None

        stale_dashboard_monitor = _monitor(tmp_path, chain_path, policy_path)
        stale_dashboard_monitor.load_metadata()
        dashboard_monitor = _monitor(tmp_path, chain_path, policy_path)
        dashboard_monitor.acknowledge_policy_rules_change(operator="dashboard")

        ChainRecorder(
            chain_path,
            integrity_monitor=stale_dashboard_monitor,
        ).append_atomic(_record("policy-acknowledged-event"))

        metadata = proxy_monitor.load_metadata()
        assert metadata["policy_rules_blocked_hash"] is None
        assert metadata["blocked_reason"] is None
        assert proxy_monitor.check_policy_rules_unchanged() is None


# ===========================================================================
# SCOPE 8 — INV-008 replay outcome verification (G-13)
# ===========================================================================

class TestINV008ReplayOutcome:
    """INV-008: Verify that replaying stored inputs through the
    evaluator produces the same decision as the original.

    Approach: create a decision record via the mediation pipeline,
    extract the classification from it, re-evaluate against the same
    policy, and confirm the outcome matches.
    """

    def test_replay_allow_decision_matches(self, tmp_path):
        """Replay an ALLOW decision — replayed outcome matches original."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        policy = {
            "rules": [
                {
                    "id": "read-all-allow",
                    "match": {"action_type": ["read"], "confidence_tier": [1, 2]},
                    "decision": "ALLOW",
                    "reason": "Test allow",
                }
            ],
            "default_decision": "DENY",
            "base_dirs": [str(tmp_path)],
            "deny_hidden_paths": True,
            "deny_executable_outputs": True,
        }

        original = mediate_decision(
            "Read",
            {"file_path": str(tmp_path / "test.txt")},
            policy=policy,
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )
        assert original["policy_decision"] == "ALLOW"

        # Extract classification from the stored record and replay
        from classifier import classify
        from policy_eval_v2 import evaluate

        replayed_cls = classify("Read", {"file_path": str(tmp_path / "test.txt")})
        replayed = evaluate(replayed_cls, policy)

        assert replayed["policy_decision"] == original["policy_decision"], (
            f"Replay mismatch: original={original['policy_decision']}, "
            f"replayed={replayed['policy_decision']}"
        )
        assert replayed["matched_rule"] == original["matched_rule"]

    def test_replay_deny_decision_matches(self, tmp_path):
        """Replay a DENY decision — replayed outcome matches original."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        policy = {
            "rules": [],
            "default_decision": "DENY",
            "default_reason": "No matching rule",
            "base_dirs": [str(tmp_path)],
            "deny_hidden_paths": True,
            "deny_executable_outputs": True,
        }

        original = mediate_decision(
            "Write",
            {"file_path": "/outside/repo/file.txt", "content": "x"},
            policy=policy,
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )
        assert original["policy_decision"] == "DENY"

        # Replay
        from classifier import classify
        from policy_eval_v2 import evaluate

        replayed_cls = classify("Write", {"file_path": "/outside/repo/file.txt", "content": "x"})
        replayed = evaluate(replayed_cls, policy)

        assert replayed["policy_decision"] == original["policy_decision"]

    def test_replay_from_chain_record_matches(self, tmp_path):
        """Read a record from the chain file, extract inputs, replay.

        This tests the full round-trip: mediation → chain write →
        chain read → replay → comparison.
        """
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        policy = {
            "rules": [
                {
                    "id": "read-allow",
                    "match": {"action_type": ["read"], "confidence_tier": [1, 2]},
                    "decision": "ALLOW",
                    "reason": "Test",
                }
            ],
            "default_decision": "DENY",
            "base_dirs": [str(tmp_path)],
            "deny_hidden_paths": True,
            "deny_executable_outputs": True,
        }

        mediate_decision(
            "Read",
            {"file_path": str(tmp_path / "data.txt")},
            policy=policy,
            chain_recorder=recorder,
            integrity_monitor=monitor,
        )

        # Read the record from chain
        records = _read_chain(chain_path)
        mediated = [r for r in records if r.get("record_type") == "mediated_decision"]
        assert len(mediated) >= 1
        stored = mediated[0]

        # Extract classification and replay
        from classifier import classify
        from policy_eval_v2 import evaluate

        replayed_cls = classify(stored["original_tool"], {"file_path": str(tmp_path / "data.txt")})
        replayed = evaluate(replayed_cls, policy)

        assert replayed["policy_decision"] == stored["policy_decision"]
        assert replayed["matched_rule"] == stored["matched_rule"]
        assert replayed["classification"]["action_type"] == stored["classification"]["action_type"]


# ===========================================================================
# SCOPE 9 — D-218: Dashboard writes do not desync integrity metadata
# ===========================================================================

class TestDashboardChainWriteSync:
    """D-218: Verify that dashboard chain writes keep integrity metadata
    in sync so that the proxy's integrity monitor does not raise
    chain_record_count_mismatch on subsequent writes.
    """

    def _dashboard_append(self, chain_path: Path, event: dict):
        """Simulate dashboard's _append_chain_record_atomic (with fix)."""
        import stat as _stat
        from event_model import _compute_event_record_hash

        chain_path.parent.mkdir(parents=True, exist_ok=True)
        # Read head hash
        head_hash = None
        if chain_path.exists():
            lines = chain_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                try:
                    head_hash = json.loads(lines[-1]).get("record_hash")
                except json.JSONDecodeError:
                    pass
        event["prev_record_hash"] = head_hash
        if "signature" not in event:
            event["signature"] = None
        if "signing_key_id" not in event:
            event["signing_key_id"] = None
        event["record_hash"] = _compute_event_record_hash(event)
        line = json.dumps(event, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) + "\n"
        fd = os.open(str(chain_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                      _stat.S_IRUSR | _stat.S_IWUSR)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def _dashboard_event(self, label: str) -> dict:
        """Build a minimal non-action event like the dashboard produces."""
        return {
            "record_version": "2.0",
            "record_type": "non_action_event",
            "event_type": "test_dashboard_event",
            "timestamp_utc": "2026-05-05T00:00:00Z",
            "payload": {"label": label},
            "prev_record_hash": None,
            "record_hash": None,
            "signature": None,
            "signing_key_id": None,
        }

    def test_dashboard_write_without_refresh_rebaselines(self, tmp_path):
        """A valid dashboard write without sidecar refresh no longer blocks."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Proxy writes a record (updates metadata)
        recorder.append_atomic(_record("proxy-1"))

        # Dashboard writes WITHOUT refreshing metadata
        self._dashboard_append(chain_path, self._dashboard_event("dash-1"))
        # Metadata still says count=1, but chain has count=2

        # Proxy's next check should accept the valid chain and refresh metadata.
        summary = monitor.verify_chain_writable()

        assert summary.record_count == 2
        assert (monitor.load_metadata() or {})["expected_record_count"] == 2

    def test_dashboard_write_with_refresh_no_mismatch(self, tmp_path):
        """With metadata refresh after write, no integrity violation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Proxy writes a record (updates metadata)
        recorder.append_atomic(_record("proxy-1"))

        # Dashboard writes AND refreshes metadata (the fix)
        self._dashboard_append(chain_path, self._dashboard_event("dash-1"))
        monitor.refresh_after_chain_write()

        # Proxy's next verify_chain_writable should succeed
        summary = monitor.verify_chain_writable()
        assert summary.record_count == 2

        # Proxy can write again without error
        recorder.append_atomic(_record("proxy-2"))
        records = _read_chain(chain_path)
        assert len(records) == 3

    def test_interleaved_proxy_dashboard_writes(self, tmp_path):
        """Multiple interleaved writes from proxy and dashboard stay in sync."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Simulate realistic interleaved write pattern
        recorder.append_atomic(_record("proxy-1"))
        self._dashboard_append(chain_path, self._dashboard_event("dash-1"))
        monitor.refresh_after_chain_write()
        recorder.append_atomic(_record("proxy-2"))
        self._dashboard_append(chain_path, self._dashboard_event("dash-2"))
        monitor.refresh_after_chain_write()
        self._dashboard_append(chain_path, self._dashboard_event("dash-3"))
        monitor.refresh_after_chain_write()
        recorder.append_atomic(_record("proxy-3"))

        records = _read_chain(chain_path)
        assert len(records) == 6

        # Verify full chain linkage
        for i in range(1, len(records)):
            assert records[i]["prev_record_hash"] == records[i - 1]["record_hash"]

    def test_startup_after_dashboard_writes_no_violation(self, tmp_path):
        """Proxy restart after dashboard writes should not raise violation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Proxy writes
        recorder.append_atomic(_record("proxy-1"))

        # Dashboard writes with metadata refresh (the fix)
        self._dashboard_append(chain_path, self._dashboard_event("dash-1"))
        monitor.refresh_after_chain_write()

        # Simulate proxy restart — new monitor, verify_startup_chain
        restarted_monitor = _monitor(tmp_path, chain_path)
        summary = restarted_monitor.verify_startup_chain()
        assert summary.record_count == 2


# ===========================================================================
# SCOPE 10 — D-219: Startup sequence ordering prevents stale count
# ===========================================================================

class TestStartupSequenceOrdering:
    """D-219: Verify that the startup sequence commits hashes to metadata
    AFTER startup events are written, preventing chain_record_count_mismatch
    on the first tool call.
    """

    def test_fresh_startup_then_tool_call_no_violation(self, tmp_path):
        """Full fresh startup sequence followed by tool call: no violation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Simulate record_startup_integrity_events:
        # 1. startup_hashes (no save)
        hashes = monitor.startup_hashes()
        assert hashes["current_proxy_code_hash"] is not None

        # 2. Append startup events (these call refresh_after_chain_write)
        recorder.append_atomic(_record("startup-event-1"))
        recorder.append_atomic(_record("startup-event-2"))

        # 3. commit_startup_hashes (saves code/policy hashes to metadata)
        monitor.commit_startup_hashes()

        # 4. First tool call — must NOT raise chain_record_count_mismatch
        recorder.append_atomic(_record("first-tool-call"))

        records = _read_chain(chain_path)
        assert len(records) == 3

    def test_commit_startup_hashes_preserves_count(self, tmp_path):
        """commit_startup_hashes merges into metadata without resetting count."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        monitor.startup_hashes()
        recorder.append_atomic(_record("event-1"))
        recorder.append_atomic(_record("event-2"))

        # At this point metadata has count=2 from refresh_after_chain_write
        metadata_before = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        assert metadata_before["expected_record_count"] == 2

        # commit_startup_hashes should preserve count=2
        monitor.commit_startup_hashes()

        metadata_after = json.loads(monitor.metadata_path.read_text(encoding="utf-8"))
        assert metadata_after["expected_record_count"] == 2
        assert metadata_after["proxy_code_hash"] is not None

    def test_full_startup_with_code_hash_change(self, tmp_path):
        """Startup with code hash change (3 events) then tool call: no violation."""
        chain_path = tmp_path / "decision-chain.jsonl"
        code_file = tmp_path / "server.py"
        code_file.write_text("print('v1')\n", encoding="utf-8")
        policy_path = tmp_path / "policy-rules.json"
        policy_path.write_text('{"rules":[]}\n', encoding="utf-8")

        # First run — establish baseline
        monitor1 = IntegrityMonitor(
            chain_path,
            metadata_path=tmp_path / "chain.integrity.json",
            policy_path=policy_path,
            repo_root=tmp_path,
            code_paths=[code_file],
        )
        monitor1.verify_startup_chain()
        monitor1.startup_hashes()
        monitor1.commit_startup_hashes()

        # Code changes between runs
        code_file.write_text("print('v2')\n", encoding="utf-8")

        # Second run — code hash changed → 3 events
        monitor2 = IntegrityMonitor(
            chain_path,
            metadata_path=tmp_path / "chain.integrity.json",
            policy_path=policy_path,
            repo_root=tmp_path,
            code_paths=[code_file],
        )
        monitor2.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor2)

        hashes = monitor2.startup_hashes()
        assert hashes["previous_proxy_code_hash"] is not None
        assert hashes["previous_proxy_code_hash"] != hashes["current_proxy_code_hash"]

        # 3 startup events: code_hash_changed + startup_code_hash + policy_loaded
        recorder.append_atomic(_record("code-hash-changed"))
        recorder.append_atomic(_record("startup-code-hash"))
        recorder.append_atomic(_record("policy-rules-loaded"))
        monitor2.commit_startup_hashes()

        # First tool call — no violation
        recorder.append_atomic(_record("first-tool-call"))
        records = _read_chain(chain_path)
        assert len(records) == 4

    def test_ten_tool_calls_after_startup_no_violations(self, tmp_path):
        """10 tool calls after startup with zero integrity violations."""
        chain_path = tmp_path / "decision-chain.jsonl"
        monitor = _monitor(tmp_path, chain_path)
        monitor.verify_startup_chain()
        recorder = ChainRecorder(chain_path, integrity_monitor=monitor)

        # Startup sequence
        monitor.startup_hashes()
        recorder.append_atomic(_record("startup-event-1"))
        recorder.append_atomic(_record("startup-event-2"))
        monitor.commit_startup_hashes()

        # 10 tool calls
        for i in range(10):
            recorder.append_atomic(_record(f"tool-call-{i}"))

        records = _read_chain(chain_path)
        assert len(records) == 12

        # Verify chain linkage is intact
        for i in range(1, len(records)):
            assert records[i]["prev_record_hash"] == records[i - 1]["record_hash"]
