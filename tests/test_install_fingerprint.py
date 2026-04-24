"""Tests for install fingerprint generation.

Verifies that fingerprints are always random per-machine and never
derived from the license key (which would cause collisions).
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dashboard"))

# Patch RUNTIME before importing so _get_install_fingerprint uses our temp dir
_tmpdir = tempfile.mkdtemp(dir="/private/tmp/claude-501")
_RUNTIME = Path(_tmpdir)

with patch.dict(os.environ, {}, clear=False):
    import importlib
    import dashboard.server as _srv_mod

    # Save original RUNTIME
    _ORIG_RUNTIME = _srv_mod.RUNTIME


class TestInstallFingerprint:
    def setup_method(self):
        """Reset RUNTIME to a fresh temp dir for each test."""
        self._tmpdir = Path(tempfile.mkdtemp(dir="/private/tmp/claude-501"))
        _srv_mod.RUNTIME = self._tmpdir

    def teardown_method(self):
        _srv_mod.RUNTIME = _ORIG_RUNTIME

    def test_generates_random_fingerprint(self):
        """First call generates and persists a random fingerprint."""
        fp = _srv_mod._get_install_fingerprint()
        assert len(fp) == 16  # 8 bytes hex-encoded
        assert (self._tmpdir / "install_fingerprint").exists()
        assert (self._tmpdir / "install_fingerprint").read_text().strip() == fp

    def test_returns_existing_fingerprint(self):
        """If install_fingerprint file exists, returns its contents."""
        (self._tmpdir / "install_fingerprint").write_text("existing_fp_1234")
        fp = _srv_mod._get_install_fingerprint()
        assert fp == "existing_fp_1234"

    def test_fingerprint_not_derived_from_license_key(self):
        """Even with a license key present, fingerprint must be random."""
        # Write a license file with a known key
        license_data = {"license_key": "ATST-TEST-1234-5678"}
        (self._tmpdir / "license.json").write_text(json.dumps(license_data))

        # Generate two fingerprints in separate "installs"
        fp1 = _srv_mod._get_install_fingerprint()

        # Clear the fingerprint file to simulate a second machine
        (self._tmpdir / "install_fingerprint").unlink()
        fp2 = _srv_mod._get_install_fingerprint()

        # With random generation, these should (almost certainly) differ
        # The probability of collision is 1/2^64 ≈ 5.4e-20
        assert fp1 != fp2, (
            "Two fingerprint generations with the same license key should "
            "produce different values (random, not derived from key)"
        )

    def test_fingerprint_is_hex(self):
        """Fingerprint should be valid hex."""
        fp = _srv_mod._get_install_fingerprint()
        int(fp, 16)  # raises ValueError if not valid hex
