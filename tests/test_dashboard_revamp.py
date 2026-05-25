#!/usr/bin/env python3
"""Tests for D-035: Chain integrity fix, dashboard UI revamp."""

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
MCP_DIR = REPO / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))


# ---------------------------------------------------------------------------
# Part A: Chain integrity fix
# ---------------------------------------------------------------------------

def test_check_chain_integrity_empty_chain():
    """check_chain_integrity returns ok for nonexistent chain."""
    from readout import check_chain_integrity
    result = check_chain_integrity(Path("/nonexistent/chain.jsonl"))
    assert result["status"] == "ok"
    assert result["checked"] is False
    assert result["chain_event_count"] == 0
    print("PASS: check_chain_integrity_empty_chain")


def test_check_chain_integrity_unsigned_records():
    """check_chain_integrity succeeds on unsigned records (signing not enforced during integrity check)."""
    from readout import check_chain_integrity
    from event_model import build_non_action_event

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Build a small chain of unsigned events
        e1 = build_non_action_event("usage_attestation", {
            "attestation_type": "test",
            "attestation_scope": "unit",
        }, prev_record_hash=None)
        e2 = build_non_action_event("usage_attestation", {
            "attestation_type": "test",
            "attestation_scope": "unit",
        }, prev_record_hash=e1["record_hash"])
        f.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
        f.write(json.dumps(e2, sort_keys=True, separators=(",", ":")) + "\n")
        chain_path = Path(f.name)

    try:
        result = check_chain_integrity(chain_path)
        assert result["status"] == "ok", f"Expected ok, got {result}"
        assert result["checked"] is True
        assert result["chain_event_count"] == 2
        print("PASS: check_chain_integrity_unsigned_records")
    finally:
        chain_path.unlink()


def test_check_chain_integrity_detects_tamper():
    """check_chain_integrity detects tampered hash linkage."""
    from readout import check_chain_integrity
    from event_model import build_non_action_event

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        e1 = build_non_action_event("usage_attestation", {
            "attestation_type": "test",
            "attestation_scope": "unit",
        }, prev_record_hash=None)
        # Build e2 with wrong prev_record_hash
        e2 = build_non_action_event("usage_attestation", {
            "attestation_type": "test",
            "attestation_scope": "unit",
        }, prev_record_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000")
        f.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
        f.write(json.dumps(e2, sort_keys=True, separators=(",", ":")) + "\n")
        chain_path = Path(f.name)

    try:
        result = check_chain_integrity(chain_path)
        assert result["status"] == "broken", f"Expected broken, got {result}"
        print("PASS: check_chain_integrity_detects_tamper")
    finally:
        chain_path.unlink()


def test_check_chain_integrity_restores_env():
    """check_chain_integrity restores GOV_SIGNING_DEV_MODE env var after execution."""
    from readout import check_chain_integrity

    # Case 1: env var was not set before
    os.environ.pop("GOV_SIGNING_DEV_MODE", None)
    check_chain_integrity(Path("/nonexistent/chain.jsonl"))
    assert "GOV_SIGNING_DEV_MODE" not in os.environ, "GOV_SIGNING_DEV_MODE should be unset"

    # Case 2: env var was set to a value before
    os.environ["GOV_SIGNING_DEV_MODE"] = "0"
    check_chain_integrity(Path("/nonexistent/chain.jsonl"))
    assert os.environ.get("GOV_SIGNING_DEV_MODE") == "0", "GOV_SIGNING_DEV_MODE should be restored to '0'"
    os.environ.pop("GOV_SIGNING_DEV_MODE", None)

    print("PASS: check_chain_integrity_restores_env")


# ---------------------------------------------------------------------------
# Part B: Dashboard UI (static content checks)
# ---------------------------------------------------------------------------

def test_styles_dark_palette():
    """styles.css uses dark palette variables."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert "--bg: #1a1d23" in css, "Missing dark background color"
    assert "--surface: #22262e" in css, "Missing dark surface color"
    assert "--ink: #e4e6eb" in css, "Missing light text color"
    font_decl = css.split("font-family")[1].split(";")[0]
    assert "sans-serif" in font_decl, "Should use sans-serif font family"
    print("PASS: styles_dark_palette")


def test_styles_tooltip_classes():
    """styles.css includes tooltip CSS classes."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert ".has-tooltip" in css, "Missing .has-tooltip class"
    assert ".tooltip-text" in css, "Missing .tooltip-text class"
    print("PASS: styles_tooltip_classes")


def test_styles_clickable_row():
    """styles.css includes clickable row styles."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert ".clickable-row" in css, "Missing .clickable-row class"
    assert ".activity-entry.clickable" in css, "Missing clickable activity entry"
    print("PASS: styles_clickable_row")


def test_app_js_tooltips():
    """app.js contains tooltip helper and uses tooltips on status cards."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert "function tip(" in js, "Missing tip() helper"
    assert "has-tooltip" in js, "Tooltips not used in HTML output"
    assert "tooltip-text" in js, "Tooltip text class not referenced"
    # Check that key metrics have tooltips
    assert "Chain Events" in js, "Missing Chain Events tooltip"
    assert "Chain Integrity" in js, "Missing Chain Integrity tooltip"
    assert "DENY Rate" in js, "Missing DENY Rate tooltip"
    print("PASS: app_js_tooltips")


def test_app_js_terminology():
    """app.js uses updated terminology (v2)."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert "categoryLabel" in js, "Missing categoryLabel function"
    assert '"Mediated Decision"' in js, "Missing 'Mediated Decision' label"
    assert '"Verification Change"' in js, "Missing 'Verification Change' label"
    assert '"Invocation Decision"' in js, "Missing 'Invocation Decision' label"
    assert '"Boundary Observation"' not in js, "Removed v2 observation label should not be present"
    # Confirm v2 terminology in overview
    assert "Mediated Operations" in js, "Missing 'Mediated Operations' card label"
    assert "Approval-Gated Operations" in js, "Missing 'Approval-Gated Operations' card label"
    # Confirm v2 record rendering
    assert "tierBadge" in js, "Missing tierBadge function for confidence tier display"
    assert "Confidence Tier" in js, "Missing confidence tier in record detail"
    print("PASS: app_js_terminology")


def test_app_js_clickable_activity():
    """app.js makes activity entries and table rows clickable."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert "clickable-row" in js, "Missing clickable-row class in table rows"
    assert 'class="activity-entry' in js, "Missing activity-entry class"
    assert "clickable" in js, "Missing clickable class on activity entries"
    print("PASS: app_js_clickable_activity")


def test_app_js_overview_explainer():
    """app.js overview page has an explainer paragraph."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert "explainer" in js, "Missing explainer class"
    assert "tamper-evident log" in js, "Missing explainer content about tamper-evident log"
    print("PASS: app_js_overview_explainer")


def test_app_js_atested_title():
    """app.js uses 'Atested Dashboard' title."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert "Atested Dashboard" in js
    html = (REPO / "dashboard" / "ui" / "index.html").read_text()
    assert "Atested Dashboard" in html
    print("PASS: app_js_atested_title")


# ---------------------------------------------------------------------------
# D-036: Chain integrity API and font alignment
# ---------------------------------------------------------------------------

def test_chain_integrity_api_returns_ok():
    """assemble_governance_status_record returns chain_integrity=ok for fresh chain."""
    from readout import assemble_governance_status_record, load_chain_rows
    from verification import VerificationStateTracker
    from approval_store import ApprovalStore
    from event_model import build_non_action_event

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        e1 = build_non_action_event("usage_attestation", {
            "attestation_type": "test",
            "attestation_scope": "unit",
        }, prev_record_hash=None)
        f.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
        chain_path = Path(f.name)

    try:
        status = assemble_governance_status_record(
            chain_path, VerificationStateTracker(), ApprovalStore()
        )
        assert status["chain_integrity"] == "ok", f"Expected ok, got {status['chain_integrity']}"
        assert status["chain_event_count"] == 1
        print("PASS: chain_integrity_api_returns_ok")
    finally:
        chain_path.unlink()


def test_fonts_inter_in_css():
    """styles.css uses Inter font family."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert '"Inter"' in css, "Missing Inter font in styles.css"
    print("PASS: fonts_inter_in_css")


def test_fonts_jetbrains_mono_in_css():
    """styles.css uses JetBrains Mono for code elements."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert '"JetBrains Mono"' in css, "Missing JetBrains Mono font in styles.css"
    print("PASS: fonts_jetbrains_mono_in_css")


def test_fonts_loaded_in_html():
    """index.html loads Inter and JetBrains Mono from Google Fonts."""
    html = (REPO / "dashboard" / "ui" / "index.html").read_text()
    assert "fonts.googleapis.com" in html, "Missing Google Fonts link in index.html"
    assert "Inter" in html, "Missing Inter in Google Fonts link"
    assert "JetBrains+Mono" in html or "JetBrains%20Mono" in html, "Missing JetBrains Mono in Google Fonts link"
    print("PASS: fonts_loaded_in_html")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_check_chain_integrity_empty_chain()
    test_check_chain_integrity_unsigned_records()
    test_check_chain_integrity_detects_tamper()
    test_check_chain_integrity_restores_env()
    test_styles_dark_palette()
    test_styles_tooltip_classes()
    test_styles_clickable_row()
    test_app_js_tooltips()
    test_app_js_terminology()
    test_app_js_clickable_activity()
    test_app_js_overview_explainer()
    test_app_js_atested_title()
    test_chain_integrity_api_returns_ok()
    test_fonts_inter_in_css()
    test_fonts_jetbrains_mono_in_css()
    test_fonts_loaded_in_html()
    print(f"\nAll 16 tests passed.")
