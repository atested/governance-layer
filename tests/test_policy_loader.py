#!/usr/bin/env python3
"""
test_policy_loader.py — Tests for the proxy base_dirs loader.

Exercises resolve_policy_base_dirs() which is the real substitution and
safety-fallback function called by GovernanceProxy._load_default_policy().
These tests cover the production loading path that was previously untested,
as identified by D-2026-0413-BASE-DIRS-MATCHER-INVESTIGATION.
"""

import logging
import sys
from pathlib import Path

# Add proxy package to path so we can import the real function.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "proxy"))

from server import resolve_policy_base_dirs

# Fixed test values for repo and runtime paths.
REPO_PATH = "/test/repo"
RUNTIME_PATH = "/test/runtime"


def test_a_both_placeholders_only():
    """JSON with both placeholders and no additional entries."""
    raw = ["__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    assert result == [REPO_PATH, RUNTIME_PATH]


def test_b_placeholders_plus_literals():
    """JSON with both placeholders and four additional literal paths."""
    raw = [
        "__GOV_CANONICAL_REPO_PATH__",
        "__GOV_RUNTIME_PATH__",
        "/Volumes/SSD/archive/project-management",
        "/Volumes/SSD/archive/gov/atested.com",
        "/Volumes/SSD/archive/Gregs-dev-code",
        "/Users/gregkeeter/transport",
    ]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    assert result == [
        REPO_PATH,
        RUNTIME_PATH,
        "/Volumes/SSD/archive/project-management",
        "/Volumes/SSD/archive/gov/atested.com",
        "/Volumes/SSD/archive/Gregs-dev-code",
        "/Users/gregkeeter/transport",
    ]


def test_c_no_placeholders_safety_fallback():
    """JSON with no placeholders but four literal paths. REPO and runtime added by safety fallback."""
    raw = [
        "/Volumes/SSD/archive/project-management",
        "/Volumes/SSD/archive/gov/atested.com",
        "/Volumes/SSD/archive/Gregs-dev-code",
        "/Users/gregkeeter/transport",
    ]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    assert REPO_PATH in result
    assert RUNTIME_PATH in result
    assert "/Volumes/SSD/archive/project-management" in result
    assert "/Volumes/SSD/archive/gov/atested.com" in result
    assert "/Volumes/SSD/archive/Gregs-dev-code" in result
    assert "/Users/gregkeeter/transport" in result
    assert len(result) == 6


def test_d_only_repo_placeholder():
    """JSON with only __GOV_CANONICAL_REPO_PATH__. Runtime added by safety fallback."""
    raw = ["__GOV_CANONICAL_REPO_PATH__"]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    assert result == [REPO_PATH, RUNTIME_PATH]


def test_e_unknown_placeholder_dropped(caplog):
    """Unknown __GOV_FOO__ placeholder is dropped with a warning."""
    raw = ["__GOV_FOO__"]
    with caplog.at_level(logging.WARNING):
        result = resolve_policy_base_dirs(
            raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
        )
    assert "__GOV_FOO__" not in result
    assert REPO_PATH in result
    assert RUNTIME_PATH in result
    assert any("Dropping unknown base_dirs placeholder" in r.message for r in caplog.records)


def test_f_literal_equals_repo_no_duplicate():
    """Literal path equal to REPO already present. No duplicate in final array."""
    raw = [
        "__GOV_CANONICAL_REPO_PATH__",
        "__GOV_RUNTIME_PATH__",
        REPO_PATH,  # duplicate of the substituted placeholder
    ]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    assert result.count(REPO_PATH) == 1
    assert result == [REPO_PATH, RUNTIME_PATH]


def test_g_substring_placeholder_not_substituted():
    """Entry containing placeholder as substring is NOT substituted (whole-string only)."""
    malformed = "/some/path/__GOV_CANONICAL_REPO_PATH__/x"
    raw = [malformed]
    result = resolve_policy_base_dirs(
        raw, repo_path=REPO_PATH, runtime_path=RUNTIME_PATH
    )
    # The malformed entry passes through as a literal.
    assert malformed in result
    # Safety fallback adds repo and runtime.
    assert REPO_PATH in result
    assert RUNTIME_PATH in result
