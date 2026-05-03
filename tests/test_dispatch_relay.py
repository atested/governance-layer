"""Tests for the dispatch relay service.

D-072 Fix 3: Dispatch relay must refuse to start without auth token.
Also adds lifecycle transition tests since the service had zero coverage.

NOTE: The dispatch relay requires its own venv (services/dispatch-relay/.venv)
with mcp, starlette, and uvicorn. Subprocess tests use that venv's Python.
In-process tests that need these dependencies are skipped if unavailable.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RELAY_DIR = REPO / "services" / "dispatch-relay"
RELAY_MODULE = RELAY_DIR / "server.py"
RELAY_PYTHON = RELAY_DIR / ".venv" / "bin" / "python3"


def _relay_python_available():
    return RELAY_PYTHON.exists() and RELAY_MODULE.exists()


# ---------------------------------------------------------------------------
# Startup enforcement (subprocess tests using relay's venv)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _relay_python_available(), reason="Relay venv not available")
class TestStartupEnforcement:
    """Verify relay refuses to start without DISPATCH_BEARER_TOKEN."""

    def test_startup_fails_without_bearer_token(self):
        """Relay exits with error when DISPATCH_BEARER_TOKEN is unset."""
        env = os.environ.copy()
        env.pop("DISPATCH_BEARER_TOKEN", None)
        env["DISPATCH_PORT"] = "0"
        proc = subprocess.run(
            [str(RELAY_PYTHON), str(RELAY_MODULE)],
            capture_output=True, text=True, timeout=10,
            cwd=str(RELAY_DIR), env=env,
        )
        assert proc.returncode != 0, f"Relay should have failed but returned rc={proc.returncode}"
        assert "bearer token" in proc.stderr.lower() or "DISPATCH_BEARER_TOKEN" in proc.stderr, \
            f"Expected bearer token error in stderr: {proc.stderr[-500:]}"

    def test_startup_fails_with_empty_bearer_token(self):
        """Relay exits with error when DISPATCH_BEARER_TOKEN is empty string."""
        env = os.environ.copy()
        env["DISPATCH_BEARER_TOKEN"] = ""
        env["DISPATCH_PORT"] = "0"
        proc = subprocess.run(
            [str(RELAY_PYTHON), str(RELAY_MODULE)],
            capture_output=True, text=True, timeout=10,
            cwd=str(RELAY_DIR), env=env,
        )
        assert proc.returncode != 0


# ---------------------------------------------------------------------------
# Auth + lifecycle tests (run as subprocess script in relay's venv)
# ---------------------------------------------------------------------------

_AUTH_AND_LIFECYCLE_SCRIPT = '''
"""Subprocess test script for dispatch relay auth and lifecycle."""
import json
import os
import sys
import tempfile

# Set env before importing the relay module
TOKEN = "test-secret-xyz"
os.environ["DISPATCH_BEARER_TOKEN"] = TOKEN
db_dir = tempfile.mkdtemp()
os.environ["DISPATCH_DB_PATH"] = os.path.join(db_dir, "test.db")

# Add relay dir to path so we can import server module
RELAY_DIR = os.environ.get("RELAY_DIR", "")
if RELAY_DIR:
    sys.path.insert(0, RELAY_DIR)

# Now import
from server import (
    _init_db, mcp_server, BearerAuthMiddleware,
    submit_dispatch, list_dispatches, claim_dispatch, complete_dispatch,
    BEARER_TOKEN,
)

errors = []

def check(name, condition, msg=""):
    if not condition:
        errors.append(f"FAIL: {name}: {msg}")
    else:
        print(f"PASS: {name}")

# --- Auth tests (using Starlette TestClient) ---
from starlette.testclient import TestClient

_init_db()
app = mcp_server.streamable_http_app()
app.add_middleware(BearerAuthMiddleware)
client = TestClient(app, raise_server_exceptions=False)

# Test: no token → 401
resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
check("no_token_401", resp.status_code == 401, f"got {resp.status_code}")

# Test: wrong token → 401
resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                   headers={"Authorization": "Bearer wrong-token"})
check("wrong_token_401", resp.status_code == 401, f"got {resp.status_code}")

# Test: valid token → not 401
resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                   headers={"Authorization": f"Bearer {TOKEN}"})
check("valid_token_passes", resp.status_code != 401, f"got {resp.status_code}")

# --- Lifecycle tests ---

# Submit
r = json.loads(submit_dispatch("D-001", "cecil", "BUILD", "Test", "body"))
check("submit_ok", r.get("ok") is True, str(r))

# Duplicate submit
r = json.loads(submit_dispatch("D-001", "cecil", "BUILD", "Test2", "body2"))
check("duplicate_rejected", "error" in r, str(r))

# Claim
r = json.loads(claim_dispatch("D-001", "cecil"))
check("claim_ok", r.get("status") == "claimed", str(r))

# Double claim
r = json.loads(claim_dispatch("D-001", "other"))
check("double_claim_rejected", "error" in r, str(r))

# Complete
r = json.loads(complete_dispatch("D-001", "success", "Done"))
check("complete_ok", r.get("ok") is True, str(r))

# Complete already completed
r = json.loads(complete_dispatch("D-001", "success", "Again"))
check("double_complete_rejected", "error" in r, str(r))

# Complete pending (skip claim)
json.loads(submit_dispatch("D-002", "cecil", "BUILD", "Test", "body"))
r = json.loads(complete_dispatch("D-002", "success", "Done"))
check("complete_pending_rejected", "error" in r and "pending" in r["error"], str(r))

# Claim nonexistent
r = json.loads(claim_dispatch("D-NONE", "cecil"))
check("claim_nonexistent_rejected", "error" in r and "not found" in r["error"], str(r))

# List filters
json.loads(submit_dispatch("D-003", "codex", "INVESTIGATE", "Test", "body"))
all_d = json.loads(list_dispatches())
check("list_all", len(all_d) >= 3, f"got {len(all_d)}")

cecil_d = json.loads(list_dispatches(target_agent="cecil"))
check("list_filter_agent", all(d["target_agent"] == "cecil" for d in cecil_d), str(cecil_d))

pending_d = json.loads(list_dispatches(status="pending"))
check("list_filter_status", all(d["status"] == "pending" for d in pending_d), str(pending_d))

# Summary
if errors:
    print("\\n".join(errors), file=sys.stderr)
    sys.exit(1)
else:
    print(f"\\nAll {14} checks passed")
'''


@pytest.mark.skipif(not _relay_python_available(), reason="Relay venv not available")
class TestAuthAndLifecycle:
    """Run auth and lifecycle tests in relay's venv via subprocess."""

    def test_auth_and_lifecycle(self, tmp_path):
        """Run comprehensive auth + lifecycle test script in relay venv."""
        script_path = tmp_path / "test_relay_script.py"
        script_path.write_text(_AUTH_AND_LIFECYCLE_SCRIPT)

        env = os.environ.copy()
        env["DISPATCH_BEARER_TOKEN"] = "test-secret-xyz"
        env["DISPATCH_DB_PATH"] = str(tmp_path / "test.db")
        env["RELAY_DIR"] = str(RELAY_DIR)

        proc = subprocess.run(
            [str(RELAY_PYTHON), str(script_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(RELAY_DIR), env=env,
        )
        if proc.returncode != 0:
            pytest.fail(
                f"Auth/lifecycle tests failed (rc={proc.returncode}):\n"
                f"stdout: {proc.stdout}\n"
                f"stderr: {proc.stderr}"
            )
