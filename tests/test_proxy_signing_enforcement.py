"""Tests for proxy signing key enforcement (INV-005).

D-072 Fix 2: Proxy must refuse to start without a valid signing key.
No silent degradation — missing key = startup failure.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


class TestProxySigningKeyEnforcement:
    """Verify proxy startup fails without a valid signing key."""

    def _run_proxy_main(self, env_overrides: dict, timeout: float = 10.0):
        """Run proxy main() in a subprocess with given env, return (returncode, stderr)."""
        env = os.environ.copy()
        # Clear any existing signing key config
        env.pop("GOV_SIGNING_KEY_PATH", None)
        env.update(env_overrides)
        # Ensure required paths
        env.setdefault("GOV_CANONICAL_REPO_PATH", str(REPO))
        env.setdefault("GOV_RUNTIME_PATH", "/tmp/gov_runtime_test")

        proc = subprocess.run(
            [sys.executable, "-m", "proxy.server", "--port", "0"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(REPO), env=env,
        )
        return proc.returncode, proc.stderr

    def test_startup_fails_without_signing_key_path(self):
        """Proxy exits with error when GOV_SIGNING_KEY_PATH is unset."""
        rc, stderr = self._run_proxy_main({"GOV_SIGNING_KEY_PATH": ""})
        assert rc != 0, f"Proxy should have failed but returned rc={rc}"
        assert "signing key" in stderr.lower() or "INV-005" in stderr, \
            f"Expected signing key error in stderr: {stderr[-500:]}"

    def test_startup_fails_with_missing_key_file(self):
        """Proxy exits with error when key path points to nonexistent file."""
        rc, stderr = self._run_proxy_main({
            "GOV_SIGNING_KEY_PATH": "/tmp/nonexistent-key-file-abc123.pem",
        })
        assert rc != 0, f"Proxy should have failed but returned rc={rc}"
        assert "signing key" in stderr.lower() or "INV-005" in stderr, \
            f"Expected signing key error in stderr: {stderr[-500:]}"

    def test_startup_succeeds_with_valid_key(self):
        """Proxy loads signing key and proceeds past the enforcement check.

        We verify that the key loads by checking it doesn't exit with a
        signing key error. It will fail later (e.g., port binding) — that's
        fine; we just need to confirm it gets past the key check.
        """
        key_path = REPO / "keys" / "governance-signing.pem"
        if not key_path.exists():
            pytest.skip("No signing key at expected path")

        rc, stderr = self._run_proxy_main({
            "GOV_SIGNING_KEY_PATH": str(key_path),
            # Use port 0 so it will try to bind but may fail — that's OK
        })
        # It may fail for other reasons (port, missing API key, etc.)
        # but should NOT fail with signing key error
        if rc != 0:
            assert "signing key" not in stderr.lower() and "INV-005" not in stderr, \
                f"Proxy failed due to signing key even with valid key: {stderr[-500:]}"
