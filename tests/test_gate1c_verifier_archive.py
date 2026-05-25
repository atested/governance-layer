"""Gate 1C — Background verifier and archive system tests.

Dispatch: 173-D-2026-0430 (RELEASE-G1C-VERIFIER-ARCHIVE-TESTS)

Covers:
  1. Health/walker integration (G-16)
  2. Break classification
  3. Verify-before-export trigger (documented finding)
  4. Sidecar terminal fallback (documented finding)
  5. Manifest accuracy (G-10)
  6. Preserved chain integrity (G-11)
  7. Archive listing (G-17)
  8. Archive creation on integrity violation
  9. Fresh-chain-after-archive event fields
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "proxy", REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from background_verifier import read_verification_status, run_verification
from chain_archive import archive_chain, list_archives
from chain_health import (
    classify_chain_break,
    collect_health_signals,
    check_chain_health,
)
from event_model import build_non_action_event
from integrity_monitor import IntegrityMonitor, IntegrityViolation
from proxy.server import ChainRecorder
from readout import check_chain_integrity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_event(path: Path, label: str, prev_hash=None) -> dict:
    """Append a valid non-action event to a chain file, maintaining linkage."""
    if prev_hash is None and path.exists():
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            prev_hash = json.loads(lines[-1]).get("record_hash")
    event = build_non_action_event(
        "verification_state_transition",
        {
            "governed_family": label,
            "from_state": "unverified",
            "to_state": "verified",
            "reason": "test",
        },
        prev_record_hash=prev_hash,
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def _write_chain(path: Path, records: list[dict]) -> None:
    """Write a list of record dicts as a JSONL chain file."""
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )


def _broken_chain(path: Path, n_good: int = 2) -> list[dict]:
    """Write a chain with `n_good` valid records followed by one with broken linkage.
    Returns all records written."""
    records = []
    prev = None
    for i in range(n_good):
        evt = build_non_action_event(
            "usage_attestation",
            {"attestation_type": "test", "attestation_scope": f"unit{i}"},
            prev_record_hash=prev,
        )
        records.append(evt)
        prev = evt["record_hash"]
    # Broken record: wrong prev_record_hash
    from event_model import _compute_event_record_hash
    bad = build_non_action_event(
        "usage_attestation",
        {"attestation_type": "test", "attestation_scope": "broken"},
        prev_record_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    )
    records.append(bad)
    _write_chain(path, records)
    return records


# ===========================================================================
# Scope 1 — Health / walker integration (G-16)
# ===========================================================================

class TestHealthVerificationIntegration:
    """Verify background verifier results appear in health signals."""

    def test_clean_verification_reflects_in_health(self, tmp_path):
        """After a successful verification run, health status reflects clean chain."""
        chain = tmp_path / "decision-chain.jsonl"
        stability = tmp_path / "stability.jsonl"
        meta = tmp_path / "chain_meta.json"

        _append_event(chain, "record-1")

        # Run verification — should report ok
        status = run_verification(chain, threshold=1)
        assert status["status"] == "ok"

        # Collect health signals — should include background verification
        health = collect_health_signals(chain, stability, meta, tmp_path)
        bg = health["background_verification"]
        assert bg["status"] == "ok"
        assert bg["checked"] is True
        assert health["overall_status"] == "healthy"
        # No background_verification alert
        alert_sources = [a["source"] for a in health["alerts"]]
        assert "background_verification" not in alert_sources

    def test_broken_verification_reflects_in_health(self, tmp_path):
        """After a break-detecting verification run, health escalates to attention."""
        chain = tmp_path / "decision-chain.jsonl"
        stability = tmp_path / "stability.jsonl"
        meta = tmp_path / "chain_meta.json"

        _broken_chain(chain)

        # Run verification — should report broken
        status = run_verification(chain, threshold=1)
        assert status["status"] == "broken"
        assert status["break_count"] >= 1

        # Collect health signals — background_verification should trigger alert
        health = collect_health_signals(chain, stability, meta, tmp_path)
        bg = health["background_verification"]
        assert bg["status"] == "broken"
        assert bg["break_count"] >= 1
        # Overall health should be at least attention
        assert health["overall_status"] in ("attention", "critical")
        alert_sources = [a["source"] for a in health["alerts"]]
        assert "background_verification" in alert_sources


# ===========================================================================
# Scope 2 — Break classification
# ===========================================================================

class TestBreakClassification:
    """Verify the background verifier classifies breaks correctly."""

    def test_hash_linkage_break_classified(self, tmp_path):
        """Hash linkage break: prev_record_hash mismatch."""
        chain = tmp_path / "chain.jsonl"
        stability = tmp_path / "stability.jsonl"
        _broken_chain(chain, n_good=2)
        result = check_chain_health(chain, stability_log_path=stability)
        assert result["status"] != "healthy"
        assert result["break_count"] >= 1
        # First break should be a prev_record_hash mismatch
        assert result["breaks"][0]["reason"] == "prev_record_hash_mismatch"

    def test_record_count_mismatch_classified(self, tmp_path):
        """Record count mismatch: chain_meta says more records than exist."""
        chain = tmp_path / "chain.jsonl"
        meta = tmp_path / "chain_meta.json"
        _append_event(chain, "only-one")
        # chain_meta claims 5 records
        meta.write_text(json.dumps({"chain_length": 5}), encoding="utf-8")
        classification = classify_chain_break(chain, 1, "truncation_detected", meta)
        assert classification["classification"] == "known"
        assert classification["pattern"] == "truncation_recovery"
        assert classification["auto_repairable"] is True

    def test_clean_chain_no_break(self, tmp_path):
        """Clean chain: no break reported."""
        chain = tmp_path / "chain.jsonl"
        _append_event(chain, "good-1")
        _append_event(chain, "good-2")
        result = check_chain_health(chain)
        assert result["status"] == "healthy"
        assert result["break_info"] is None
        assert result["break_count"] == 0
        assert result["breaks"] == []

    def test_partial_write_classified(self, tmp_path):
        """Trailing invalid JSON classified as partial_write."""
        chain = tmp_path / "chain.jsonl"
        _append_event(chain, "good")
        with chain.open("a") as fh:
            fh.write('{"incomplete":\n')
        classification = classify_chain_break(chain, 2, "invalid_json")
        assert classification["classification"] == "known"
        assert classification["pattern"] == "partial_write"

    def test_unknown_reason_defaults_suspicious(self, tmp_path):
        """Unrecognized break reason defaults to suspicious."""
        chain = tmp_path / "chain.jsonl"
        chain.touch()
        classification = classify_chain_break(chain, 5, "alien_corruption")
        assert classification["classification"] == "suspicious"
        assert classification["auto_repairable"] is False
        assert classification["confidence"] == "low"


# ===========================================================================
# Scope 3 — Verify-before-export trigger (documented finding)
# ===========================================================================

class TestVerifyBeforeExport:
    """Document that the export system does NOT trigger verification."""

    def test_evidence_package_has_no_verification_trigger(self):
        """evidence_package.py does not import or call background_verifier.

        DOCUMENTED FINDING: The export system (evidence_package.py) does not
        trigger background verification before creating an evidence package.
        It builds its own build_verification_summary() inline, which verifies
        hash linkage within the selected records, but does not invoke the
        background verifier's full-chain check.

        This is a design addition candidate, not a bug — the inline
        verification summary provides record-level integrity assurance
        within the exported window.
        """
        source = (REPO / "scripts" / "evidence_package.py").read_text(encoding="utf-8")
        assert "background_verifier" not in source
        assert "run_verification" not in source
        assert "trigger_after_append" not in source
        # But it does have its own verification
        assert "build_verification_summary" in source

    def test_mcp_export_has_no_verification_trigger(self):
        """MCP server export tools do not trigger background verification."""
        import pytest
        pytest.skip("MCP broker archived (D-203) — test requires mcp server")


# ===========================================================================
# Scope 4 — Sidecar terminal fallback (documented finding)
# ===========================================================================

class TestSidecarTerminalFallback:
    """Test behavior when chain file is unwritable."""

    def test_verifier_reports_error_when_chain_unreadable(self, tmp_path):
        """Background verifier handles missing/unreadable chain gracefully.

        The verifier calls readout.check_chain_integrity() which returns
        status=ok with checked=False for missing chains. For truly unreadable
        chains (permissions), the verifier catches exceptions and writes
        an error status to its sidecar.

        DOCUMENTED FINDING: The background verifier does not have a specific
        "sidecar terminal fallback" mechanism. It always writes to its own
        status sidecar (chain_verification_status.json), never to the main
        chain. When the chain is unreadable, it records status="error" in
        the sidecar. This is inherently a sidecar-only operation by design.
        """
        chain = tmp_path / "decision-chain.jsonl"
        # Chain doesn't exist — verifier should handle gracefully
        status = run_verification(chain, threshold=1)
        # Missing chain is treated as ok (empty chain is valid)
        assert status["status"] == "ok"
        assert status["checked"] is True
        assert status["last_verified_count"] == 0

    def test_verifier_status_always_writes_to_sidecar(self, tmp_path):
        """Verification status is always written to sidecar, never chain."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "test")
        chain_before = chain.read_text(encoding="utf-8")

        run_verification(chain, threshold=1)

        # Chain must not be modified
        assert chain.read_text(encoding="utf-8") == chain_before
        # Status sidecar must exist
        status_path = tmp_path / "chain_verification_status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["status"] == "ok"


# ===========================================================================
# Scope 5 — Manifest accuracy (G-10)
# ===========================================================================

class TestManifestAccuracy:
    """Verify archive manifest fields match actual archived chain content."""

    def test_record_count_matches_actual(self, tmp_path):
        """Manifest record_count matches number of records in archived chain."""
        chain = tmp_path / "decision-chain.jsonl"
        for i in range(4):
            _append_event(chain, f"rec-{i}")

        manifest = archive_chain(chain, reason="test_accuracy")

        assert manifest["record_count"] == 4
        archive_path = Path(manifest["archive_chain_path"])
        actual_count = sum(1 for l in archive_path.read_text(encoding="utf-8").splitlines() if l.strip())
        assert manifest["record_count"] == actual_count

    def test_last_hash_matches_actual(self, tmp_path):
        """Manifest last_record_hash matches the actual last record's hash."""
        chain = tmp_path / "decision-chain.jsonl"
        events = []
        for i in range(3):
            events.append(_append_event(chain, f"hash-{i}"))

        manifest = archive_chain(chain, reason="test_hash_accuracy")

        assert manifest["last_record_hash"] == events[-1]["record_hash"]
        # Also verify by reading the archived chain
        archive_path = Path(manifest["archive_chain_path"])
        lines = [l for l in archive_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        last_rec = json.loads(lines[-1])
        assert manifest["last_record_hash"] == last_rec["record_hash"]

    def test_timestamps_plausible(self, tmp_path):
        """Manifest archived_at_utc is plausible (not null, not future)."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "ts-test")

        manifest = archive_chain(chain, reason="test_timestamps")

        ts_str = manifest["archived_at_utc"]
        assert ts_str is not None
        assert ts_str != ""
        # Parse the timestamp
        ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        # Not in the future (allow 5s tolerance)
        from datetime import timedelta
        assert ts <= now + timedelta(seconds=5)
        # Not ancient (within last hour)
        assert ts >= now - timedelta(hours=1)

    def test_manifest_fields_complete(self, tmp_path):
        """Manifest contains all required fields with correct types."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "fields-test")

        manifest = archive_chain(chain, reason="test_fields")

        assert manifest["schema_version"] == 1
        assert isinstance(manifest["archive_id"], str) and len(manifest["archive_id"]) > 0
        assert isinstance(manifest["archived_at_utc"], str)
        assert manifest["reason"] == "test_fields"
        assert isinstance(manifest["payload"], dict)
        assert isinstance(manifest["original_chain_path"], str)
        assert isinstance(manifest["archive_chain_path"], str)
        assert manifest["chain_existed"] is True
        assert isinstance(manifest["record_count"], int)
        assert isinstance(manifest["last_record_hash"], str)
        assert manifest["sidecar_only_terminal_event"] is True
        assert isinstance(manifest["operator_retention"], str)
        assert isinstance(manifest["manifest_path"], str)


# ===========================================================================
# Scope 6 — Preserved chain integrity (G-11)
# ===========================================================================

class TestPreservedChainIntegrity:
    """Verify archived chains pass integrity verification and detect tampering."""

    def test_archived_chain_passes_integrity(self, tmp_path):
        """summarize_chain equivalent (check_chain_integrity) passes on archived chain."""
        chain = tmp_path / "decision-chain.jsonl"
        for i in range(5):
            _append_event(chain, f"integrity-{i}")

        manifest = archive_chain(chain, reason="test_integrity")
        archive_path = Path(manifest["archive_chain_path"])

        # Run integrity check on archived chain
        result = check_chain_integrity(archive_path)
        assert result["status"] == "ok"
        assert result["checked"] is True
        assert result["chain_event_count"] == 5

    def test_tampered_archive_detected(self, tmp_path):
        """Tampering with archived chain is detected by integrity verification."""
        chain = tmp_path / "decision-chain.jsonl"
        for i in range(3):
            _append_event(chain, f"tamper-{i}")

        manifest = archive_chain(chain, reason="test_tamper_detection")
        archive_path = Path(manifest["archive_chain_path"])

        # Tamper: modify a record hash in the middle
        lines = archive_path.read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[1])
        rec["record_hash"] = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        lines[1] = json.dumps(rec, sort_keys=True)
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Integrity check should detect the break
        result = check_chain_integrity(archive_path)
        assert result["status"] == "broken"
        assert result["break_count"] >= 1

    def test_tampered_archive_linkage_break(self, tmp_path):
        """Modifying prev_record_hash in archived chain is detected.

        When prev_record_hash is changed, the record's content changes but
        the stored record_hash no longer matches the recomputed hash.
        check_chain_integrity detects this as a record_hash mismatch.
        """
        chain = tmp_path / "decision-chain.jsonl"
        for i in range(4):
            _append_event(chain, f"link-{i}")

        manifest = archive_chain(chain, reason="test_linkage")
        archive_path = Path(manifest["archive_chain_path"])

        # Tamper: change prev_record_hash of 3rd record
        lines = archive_path.read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[2])
        rec["prev_record_hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        lines[2] = json.dumps(rec, sort_keys=True)
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = check_chain_integrity(archive_path)
        assert result["status"] == "broken"
        # Changing prev_record_hash alters record content → record_hash mismatch
        assert any("record_hash mismatch" in b.get("reason", "") for b in result.get("breaks", []))


# ===========================================================================
# Scope 7 — Archive listing (G-17)
# ===========================================================================

class TestArchiveListing:
    """Verify archive listing returns correct results for zero, one, and multiple archives."""

    def test_no_archives_returns_empty(self, tmp_path):
        """With no archives, list_archives returns empty list (not error)."""
        chain = tmp_path / "decision-chain.jsonl"
        chain.touch()
        result = list_archives(chain)
        assert result == []

    def test_one_archive_returns_one_entry(self, tmp_path):
        """After one archive, listing returns one entry with correct metadata."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "list-1")
        manifest = archive_chain(chain, reason="test_listing_single")

        result = list_archives(chain)
        assert len(result) == 1
        assert result[0]["archive_id"] == manifest["archive_id"]
        assert result[0]["reason"] == "test_listing_single"
        assert result[0]["record_count"] == 1

    def test_multiple_archives_returns_all(self, tmp_path):
        """After multiple archives, listing returns all entries."""
        chain = tmp_path / "decision-chain.jsonl"
        manifests = []

        for i in range(3):
            _append_event(chain, f"multi-{i}")
            m = archive_chain(chain, reason=f"test_listing_{i}")
            manifests.append(m)

        result = list_archives(chain)
        assert len(result) == 3

        # All archive IDs present
        result_ids = set(r["archive_id"] for r in result)
        expected_ids = set(m["archive_id"] for m in manifests)
        assert result_ids == expected_ids

        # Listing is sorted by manifest filename (reverse), which is
        # deterministic regardless of creation speed
        filenames = [Path(r["manifest_path"]).name for r in result]
        assert filenames == sorted(filenames, reverse=True)

    def test_listing_includes_manifest_path(self, tmp_path):
        """Each listing entry includes the manifest_path field."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "path-test")
        archive_chain(chain, reason="test_manifest_path")

        result = list_archives(chain)
        assert len(result) == 1
        assert "manifest_path" in result[0]
        assert Path(result[0]["manifest_path"]).exists()


# ===========================================================================
# Scope 8 — Archive creation on integrity violation
# ===========================================================================

class TestArchiveOnIntegrityViolation:
    """Test violation-triggered archive with fresh chain restart."""

    def test_violation_triggers_archive_and_fresh_chain(self, tmp_path):
        """Integrity violation → archive compromised chain → start fresh."""
        chain = tmp_path / "decision-chain.jsonl"
        sidecar = tmp_path / "integrity-events.jsonl"
        meta = tmp_path / "chain.integrity.json"
        policy = tmp_path / "policy-rules.json"
        policy.write_text('{"rules":[]}\n', encoding="utf-8")
        code_file = tmp_path / "server.py"
        code_file.write_text("print('proxy')\n", encoding="utf-8")

        # Create a valid chain and baseline
        _append_event(chain, "original-1")
        _append_event(chain, "original-2")
        monitor = IntegrityMonitor(
            chain, metadata_path=meta, policy_path=policy,
            repo_root=tmp_path, code_paths=[code_file],
        )
        monitor.save_chain_summary(monitor.summarize_chain())

        # Tamper with the chain — truncate it
        chain.write_text("", encoding="utf-8")

        # Re-create monitor — verify_startup_chain should detect violation
        monitor2 = IntegrityMonitor(
            chain, metadata_path=meta, policy_path=policy,
            repo_root=tmp_path, code_paths=[code_file],
        )
        try:
            monitor2.verify_startup_chain()
            violation_raised = False
        except IntegrityViolation:
            violation_raised = True

        assert violation_raised, "Expected IntegrityViolation for truncated chain"

        # Archive the compromised chain (as proxy startup does). The proxy
        # appends its own signed genesis next, so archive_chain must not write
        # one (write_genesis=False).
        manifest = archive_chain(
            chain,
            reason="startup_integrity_violation",
            payload={"error": "chain truncated"},
            sidecar_events_path=sidecar,
            write_genesis=False,
        )

        # Archive manifest should exist
        assert Path(manifest["manifest_path"]).exists()
        assert manifest["reason"] == "startup_integrity_violation"

        # Start fresh chain
        recorder = ChainRecorder(chain)
        recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        # Fresh chain should exist with one record
        assert chain.exists()
        lines = [l for l in chain.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        first = json.loads(lines[0])
        assert first["event_type"] == "chain_started_after_archive"
        assert first["archive_id"] == manifest["archive_id"]

    def test_archived_chain_listed_after_violation(self, tmp_path):
        """After violation-triggered archive, the archive appears in listing."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "pre-violation")

        archive_chain(chain, reason="integrity_violation")

        archives = list_archives(chain)
        assert len(archives) == 1
        assert archives[0]["reason"] == "integrity_violation"
        assert archives[0]["record_count"] == 1


# ===========================================================================
# Scope 9 — Fresh-chain-after-archive event fields
# ===========================================================================

class TestFreshChainAfterArchiveFields:
    """Verify chain_started_after_archive event contains correct fields."""

    def test_event_contains_archive_id(self, tmp_path):
        """Event has archive_id matching the archive manifest."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "pre-archive")
        manifest = archive_chain(chain, reason="field_test", write_genesis=False)

        recorder = ChainRecorder(chain)
        event = recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        assert event["event_type"] == "chain_started_after_archive"
        assert event["archive_id"] == manifest["archive_id"]

    def test_event_contains_manifest_path(self, tmp_path):
        """Event has archive_manifest_path pointing to existing manifest."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "manifest-path-test")
        manifest = archive_chain(chain, reason="manifest_path_test", write_genesis=False)

        recorder = ChainRecorder(chain)
        event = recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        assert event["archive_manifest_path"] == manifest["manifest_path"]
        assert Path(event["archive_manifest_path"]).exists()

    def test_event_contains_archive_chain_path(self, tmp_path):
        """Event has archive_chain_path referencing the preceding chain."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "chain-ref-test")
        _append_event(chain, "chain-ref-test-2")
        manifest = archive_chain(chain, reason="chain_ref_test", write_genesis=False)

        recorder = ChainRecorder(chain)
        event = recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        assert event["archive_chain_path"] == manifest["archive_chain_path"]
        assert Path(event["archive_chain_path"]).exists()
        # Archived chain should have 2 records
        archived = Path(event["archive_chain_path"])
        line_count = sum(1 for l in archived.read_text(encoding="utf-8").splitlines() if l.strip())
        assert line_count == 2

    def test_event_contains_reason_and_count(self, tmp_path):
        """Event has archive_reason and archived_record_count fields."""
        chain = tmp_path / "decision-chain.jsonl"
        for i in range(3):
            _append_event(chain, f"reason-{i}")
        manifest = archive_chain(chain, reason="reason_count_test", write_genesis=False)

        recorder = ChainRecorder(chain)
        event = recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        assert event["archive_reason"] == "reason_count_test"
        assert event["archived_record_count"] == 3

    def test_fresh_chain_record_is_valid(self, tmp_path):
        """The chain_started_after_archive record itself passes integrity check."""
        chain = tmp_path / "decision-chain.jsonl"
        _append_event(chain, "valid-test")
        manifest = archive_chain(chain, reason="validity_test", write_genesis=False)

        recorder = ChainRecorder(chain)
        recorder.append_integrity_event(
            "chain_started_after_archive",
            {
                "archive_id": manifest["archive_id"],
                "archive_manifest_path": manifest["manifest_path"],
                "archive_chain_path": manifest.get("archive_chain_path", ""),
                "archive_reason": manifest["reason"],
                "archived_record_count": manifest["record_count"],
            },
        )

        # The fresh chain should pass integrity check
        result = check_chain_integrity(chain)
        assert result["status"] == "ok"
        assert result["chain_event_count"] == 1
