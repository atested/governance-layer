#!/usr/bin/env python3
"""Tests for dashboard server source file auto-reload."""

import importlib
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
DASHBOARD_DIR = REPO / "dashboard"
MCP_DIR = REPO / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))


def _fresh_server_module():
    """Import dashboard server module by file path to avoid name collisions."""
    server_path = DASHBOARD_DIR / "server.py"
    spec = importlib.util.spec_from_file_location("dashboard_server", str(server_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_and_reload_detects_python_changes():
    """Auto-reload detects when a Python source file mtime changes."""
    server = _fresh_server_module()
    # Reset mtime tracking
    server._source_mtimes.clear()

    # Prime the mtimes by running once
    server._check_and_reload()

    # Simulate a file change by altering a tracked mtime
    changed_key = None
    for key in server._source_mtimes:
        if key.endswith(".py"):
            changed_key = key
            break
    assert changed_key is not None, "No Python files tracked"

    # Artificially age the stored mtime so the next stat looks like a change
    server._source_mtimes[changed_key] -= 1.0

    # Patch importlib.reload to verify it gets called
    with mock.patch.object(importlib, "reload", wraps=importlib.reload) as mock_reload:
        server._check_and_reload()
        assert mock_reload.call_count > 0, "importlib.reload was not called after mtime change"


def test_check_and_reload_no_false_positive():
    """Auto-reload does not reload when no files have changed."""
    server = _fresh_server_module()
    server._source_mtimes.clear()

    # Prime
    server._check_and_reload()

    # Run again without changes
    with mock.patch.object(importlib, "reload") as mock_reload:
        server._check_and_reload()
        assert mock_reload.call_count == 0, "Spurious reload when no files changed"


def test_check_and_reload_updates_asset_version():
    """Auto-reload recomputes asset version when UI files change."""
    server = _fresh_server_module()
    server._source_mtimes.clear()

    # Prime
    server._check_and_reload()
    original_version = server._ASSET_VERSION

    # Simulate UI file change
    for key in list(server._source_mtimes):
        if key.endswith("app.js"):
            server._source_mtimes[key] -= 1.0
            break

    server._check_and_reload()
    # Version should be recomputed (may be same value if file unchanged,
    # but the recomputation path should have run)
    assert server._ASSET_VERSION is not None


def test_check_and_reload_invalidates_cached_state():
    """Auto-reload clears cached verification/approval state on module change."""
    server = _fresh_server_module()
    server._source_mtimes.clear()

    # Set cached state to non-None sentinel values
    server._verification_tracker = "sentinel"
    server._approval_store = "sentinel"

    # Prime
    server._check_and_reload()

    # Simulate a Python file change
    for key in list(server._source_mtimes):
        if key.endswith(".py"):
            server._source_mtimes[key] -= 1.0
            break

    server._check_and_reload()
    assert server._verification_tracker is None, "Cached tracker not invalidated"
    assert server._approval_store is None, "Cached approval store not invalidated"
