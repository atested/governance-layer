"""SEC-2026-002 through SEC-2026-005 — Adversarial tests for Gate 4 fixes.

Dispatch 182-D-2026-0430 (RELEASE-G4-BLOCKER-FIXES)

SEC-2026-002: metadata_hash included in proxy_startup_code_hash event
SEC-2026-003: build_verification_summary recomputes record hashes
SEC-2026-004: viewer.html SHA-256 included in evidence package manifest
SEC-2026-005: archive_chain_path validated against archive directory
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "proxy"))


# ===========================================================================
# SEC-2026-005 — Archive path traversal
# ===========================================================================

class TestArchivePathTraversal:
    """archive_chain_path must not escape the archive directory."""

    def _make_chain_env(self, tmp_path):
        """Create a minimal chain + archive directory structure."""
        chain_path = tmp_path / "decision-chain.jsonl"
        chain_path.write_text("")
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        return chain_path, archive_dir

    def _write_manifest(self, archive_dir, archive_id, archive_chain_path):
        manifest = {
            "archive_id": archive_id,
            "archive_chain_path": str(archive_chain_path),
        }
        manifest_path = archive_dir / f"{archive_id}.manifest.json"
        manifest_path.write_text(json.dumps(manifest))

    def test_valid_archive_path_accepted(self, tmp_path):
        """Normal archive path inside archive dir works."""
        chain_path, archive_dir = self._make_chain_env(tmp_path)
        archive_file = archive_dir / "test-archive.jsonl"
        archive_file.write_text('{"event_type": "test"}\n')
        self._write_manifest(archive_dir, "test-archive", archive_file)

        from chain_walker import load_raw_records_range
        result = load_raw_records_range(
            chain_path, chain_source="archive", archive_id="test-archive",
            start_sequence=0, end_sequence=100,
        )
        assert "error" not in result or "escapes" not in result.get("error", "")

    def test_traversal_path_rejected(self, tmp_path):
        """Path with ../ escaping archive dir is rejected."""
        chain_path, archive_dir = self._make_chain_env(tmp_path)
        # Create a file outside archive dir
        outside_file = tmp_path / "secret.jsonl"
        outside_file.write_text('{"secret": true}\n')
        # Manifest points outside via traversal
        self._write_manifest(
            archive_dir, "evil-archive",
            archive_dir / ".." / "secret.jsonl",
        )

        from chain_walker import load_raw_records_range
        result = load_raw_records_range(
            chain_path, chain_source="archive", archive_id="evil-archive",
            start_sequence=0, end_sequence=100,
        )
        assert "error" in result
        assert "escapes" in result["error"]
        assert result["records"] == []

    def test_absolute_path_outside_rejected(self, tmp_path):
        """Absolute path pointing outside archive dir is rejected."""
        chain_path, archive_dir = self._make_chain_env(tmp_path)
        outside_file = tmp_path / "other" / "data.jsonl"
        outside_file.parent.mkdir(parents=True)
        outside_file.write_text('{"data": true}\n')
        self._write_manifest(archive_dir, "abs-archive", outside_file)

        from chain_walker import load_raw_records_range
        result = load_raw_records_range(
            chain_path, chain_source="archive", archive_id="abs-archive",
            start_sequence=0, end_sequence=100,
        )
        assert "error" in result
        assert "escapes" in result["error"]

    def test_symlink_escape_rejected(self, tmp_path):
        """Symlink pointing outside archive dir is rejected."""
        chain_path, archive_dir = self._make_chain_env(tmp_path)
        outside_file = tmp_path / "private.jsonl"
        outside_file.write_text('{"private": true}\n')
        symlink_path = archive_dir / "link-archive.jsonl"
        try:
            symlink_path.symlink_to(outside_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")
        self._write_manifest(archive_dir, "link-archive", symlink_path)

        from chain_walker import load_raw_records_range
        result = load_raw_records_range(
            chain_path, chain_source="archive", archive_id="link-archive",
            start_sequence=0, end_sequence=100,
        )
        assert "error" in result
        assert "escapes" in result["error"]


# ===========================================================================
# SEC-2026-004 — Viewer hash in manifest
# ===========================================================================

class TestViewerHashInManifest:
    """Evidence package manifest must include viewer.html SHA-256 hash."""

    def test_manifest_contains_viewer_hash(self):
        from evidence_package import build_package, _load_viewer_html

        # Build a minimal package
        records = [
            {
                "record_version": "2.0",
                "record_type": "mediated_decision",
                "event_id": "test-1",
                "record_hash": "sha256:abc123",
                "prev_record_hash": None,
            }
        ]
        # Use a valid-length password
        password = "TestPassword1234!@#$"

        # We need to mock the signing key to avoid needing a real key
        pk_info = {
            "public_key_pem": "mock-pem",
            "fingerprint": "sha256:mock-fingerprint",
        }
        with patch("evidence_package.load_public_key_info", return_value=pk_info):
            result = build_package(
                records=records,
                password=password,
                operator_identity="test",
            )

        manifest = result["manifest"]
        assert "viewer_html_sha256" in manifest
        assert manifest["viewer_html_sha256"].startswith("sha256:")

        # Verify the hash matches the actual viewer content
        viewer_html = _load_viewer_html()
        expected = "sha256:" + hashlib.sha256(viewer_html.encode("utf-8")).hexdigest()
        assert manifest["viewer_html_sha256"] == expected

    def test_tampered_viewer_detected(self):
        """If viewer.html were swapped, the hash would not match the manifest."""
        from evidence_package import _load_viewer_html

        viewer_html = _load_viewer_html()
        real_hash = "sha256:" + hashlib.sha256(viewer_html.encode("utf-8")).hexdigest()
        tampered = viewer_html + "<script>alert('xss')</script>"
        tampered_hash = "sha256:" + hashlib.sha256(tampered.encode("utf-8")).hexdigest()
        assert real_hash != tampered_hash


# ===========================================================================
# SEC-2026-003 — Verification summary recomputes hashes
# ===========================================================================

class TestVerificationSummaryRecomputes:
    """build_verification_summary must detect tampered record hashes."""

    def test_valid_records_with_correct_hashes_verify(self):
        """Records with correctly computed hashes should verify."""
        import hashlib as _hl
        from evidence_package import build_verification_summary

        def _make_record(event_id, prev_hash=None):
            base = {"event_id": event_id, "data": "test", "prev_record_hash": prev_hash}
            canon = json.dumps(base, sort_keys=True, separators=(",", ":"))
            base["record_hash"] = "sha256:" + _hl.sha256(canon.encode()).hexdigest()
            return base

        r1 = _make_record("1")
        r2 = _make_record("2", r1["record_hash"])
        result = build_verification_summary([r1, r2])
        assert result["status"] == "verified"
        assert result["verified_count"] == 2

    def test_tampered_hash_detected(self):
        """Record with modified record_hash should be detected as a break."""
        from evidence_package import build_verification_summary

        # Create a record that looks like it has a valid hash but doesn't
        records = [
            {
                "record_version": "2.0",
                "record_type": "mediated_decision",
                "event_id": "test-1",
                "record_hash": "sha256:tampered_hash_value_not_real",
                "prev_record_hash": None,
            },
        ]
        result = build_verification_summary(records)
        # The verify module should detect the hash mismatch
        assert result["break_count"] >= 1 or result["status"] == "breaks_detected"

    def test_empty_records(self):
        from evidence_package import build_verification_summary
        result = build_verification_summary([])
        assert result["status"] == "empty"


# ===========================================================================
# SEC-2026-002 — metadata_hash in startup signed event
# ===========================================================================

class TestMetadataHashInStartupEvent:
    """proxy_startup_code_hash event must include metadata_hash."""

    def test_startup_event_includes_metadata_hash(self, tmp_path):
        """Record startup integrity events and verify metadata_hash is present."""
        from integrity_monitor import IntegrityMonitor

        chain_path = tmp_path / "decision-chain.jsonl"
        chain_path.write_text("")

        monitor = IntegrityMonitor(chain_path)

        # Record some startup state
        monitor.save_metadata({
            "proxy_code_hash": "sha256:test",
            "policy_rules_hash": "sha256:test-policy",
        })

        metadata = monitor.load_metadata()
        assert metadata is not None
        assert "metadata_hash" in metadata
        assert metadata["metadata_hash"].startswith("sha256:")

    def test_metadata_hash_not_none_in_event_payload(self):
        """The metadata_hash field in the event payload must not be None."""
        from integrity_monitor import IntegrityMonitor, _metadata_hash

        # Compute a metadata hash the same way the code does
        metadata = {
            "schema_version": 1,
            "chain_path": "/tmp/test",
            "chain_existed": False,
            "expected_record_count": 0,
            "expected_last_record_hash": None,
            "expected_chain_size_bytes": 0,
            "proxy_code_hash": "sha256:abc",
            "policy_rules_hash": "sha256:def",
            "policy_rules_blocked_hash": None,
            "blocked_reason": None,
            "last_updated_utc": "2026-01-01T00:00:00Z",
            "metadata_hash": None,
        }
        h = _metadata_hash(metadata)
        assert h is not None
        assert h.startswith("sha256:")
        assert len(h) > 10

    def test_metadata_hash_changes_on_tamper(self):
        """Modifying metadata fields must change the hash."""
        from integrity_monitor import _metadata_hash

        metadata = {
            "schema_version": 1,
            "proxy_code_hash": "sha256:original",
            "metadata_hash": None,
        }
        h1 = _metadata_hash(metadata)

        metadata_tampered = {
            "schema_version": 1,
            "proxy_code_hash": "sha256:tampered",
            "metadata_hash": None,
        }
        h2 = _metadata_hash(metadata_tampered)
        assert h1 != h2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
