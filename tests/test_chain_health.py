#!/usr/bin/env python3
"""Tests for D-037: Chain health, break classification, self-healing, retention, and system health."""

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
# Break classification tests
# ---------------------------------------------------------------------------

def test_classify_unsigned_legacy():
    """Unsigned record rejection is classified as known/auto-repairable."""
    from chain_health import classify_chain_break
    result = classify_chain_break(
        Path("/dummy/chain.jsonl"), 1,
        "unsigned record rejected in GOV_SIGNING_REQUIRED=1 mode"
    )
    assert result["classification"] == "known"
    assert result["pattern"] == "unsigned_legacy"
    assert result["auto_repairable"] is True
    assert result["confidence"] == "high"
    print("PASS: classify_unsigned_legacy")


def test_classify_unknown_defaults_suspicious():
    """Unrecognized break reason defaults to suspicious."""
    from chain_health import classify_chain_break
    result = classify_chain_break(
        Path("/dummy/chain.jsonl"), 5,
        "some_completely_unknown_error"
    )
    assert result["classification"] == "suspicious"
    assert result["auto_repairable"] is False
    assert result["confidence"] == "low"
    print("PASS: classify_unknown_defaults_suspicious")


def test_classify_partial_write():
    """Trailing invalid JSON is classified as partial_write."""
    from chain_health import classify_chain_break
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"valid": true}\n')
        f.write('{"incomplete":\n')  # corrupt trailing line
        chain_path = Path(f.name)
    try:
        result = classify_chain_break(chain_path, 2, "invalid_json")
        assert result["classification"] == "known"
        assert result["pattern"] == "partial_write"
        assert result["auto_repairable"] is True
        print("PASS: classify_partial_write")
    finally:
        chain_path.unlink()


# ---------------------------------------------------------------------------
# Self-healing tests
# ---------------------------------------------------------------------------

def test_auto_repair_known_truncate():
    """Auto-repair removes corrupt trailing line for partial_write."""
    from chain_health import auto_repair_chain
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"record": 1}\n')
        f.write('{"incomplete":\n')
        chain_path = Path(f.name)
    stability_log = chain_path.with_suffix(".stability.jsonl")
    try:
        break_info = {
            "classification": "known",
            "pattern": "partial_write",
            "auto_repairable": True,
            "repair_strategy": "truncate_last_line",
        }
        result = auto_repair_chain(chain_path, break_info, stability_log)
        assert result["repaired"] is True
        assert result["strategy"] == "truncate_last_line"
        # Verify chain now has only 1 line
        with open(chain_path) as fh:
            lines = [l for l in fh if l.strip()]
        assert len(lines) == 1
        print("PASS: auto_repair_known_truncate")
    finally:
        chain_path.unlink(missing_ok=True)
        stability_log.unlink(missing_ok=True)


def test_auto_repair_refuses_suspicious():
    """Auto-repair refuses to repair suspicious breaks."""
    from chain_health import auto_repair_chain
    stability_log = Path(tempfile.mktemp(suffix=".stability.jsonl"))
    try:
        break_info = {
            "classification": "suspicious",
            "auto_repairable": False,
        }
        result = auto_repair_chain(Path("/dummy"), break_info, stability_log)
        assert result["repaired"] is False
        assert "not classified as known" in result["reason"]
        print("PASS: auto_repair_refuses_suspicious")
    finally:
        stability_log.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Pattern detection tests
# ---------------------------------------------------------------------------

def test_pattern_detection_below_threshold():
    """No pattern alert when breaks are below threshold."""
    from chain_health import detect_break_pattern
    stability_log = Path(tempfile.mktemp(suffix=".stability.jsonl"))
    # Empty log — no pattern
    assert detect_break_pattern(stability_log) is None
    print("PASS: pattern_detection_below_threshold")


def test_pattern_detection_above_threshold():
    """Pattern alert when 3+ breaks detected in window."""
    from chain_health import detect_break_pattern, append_stability_event
    stability_log = Path(tempfile.mktemp(suffix=".stability.jsonl"))
    try:
        for i in range(4):
            append_stability_event(stability_log, "break_detected", {
                "break_at_line": i + 1,
                "reason": f"test_break_{i}",
            })
        result = detect_break_pattern(stability_log, window_hours=1, threshold=3)
        assert result is not None
        assert result["pattern_detected"] is True
        assert result["break_count"] >= 3
        assert result["severity"] == "critical"
        print("PASS: pattern_detection_above_threshold")
    finally:
        stability_log.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Stability log tests
# ---------------------------------------------------------------------------

def test_stability_log_append_and_read():
    """Stability events can be written and read back."""
    from chain_health import append_stability_event, read_stability_log
    stability_log = Path(tempfile.mktemp(suffix=".stability.jsonl"))
    try:
        evt = append_stability_event(stability_log, "health_check", {"status": "ok"})
        assert "stability_event_id" in evt
        assert evt["event_type"] == "health_check"

        events = read_stability_log(stability_log)
        assert len(events) == 1
        assert events[0]["event_type"] == "health_check"
        assert events[0]["detail"]["status"] == "ok"
        print("PASS: stability_log_append_and_read")
    finally:
        stability_log.unlink(missing_ok=True)


def test_stability_log_rejects_bad_type():
    """append_stability_event rejects unknown event types."""
    from chain_health import append_stability_event
    try:
        append_stability_event(Path("/tmp/dummy.jsonl"), "bad_type", {})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "unknown stability event type" in str(e)
    print("PASS: stability_log_rejects_bad_type")


# ---------------------------------------------------------------------------
# Rolling retention tests
# ---------------------------------------------------------------------------

def test_archive_chain_segment():
    """archive_chain_segment retires old records to archive."""
    from chain_health import archive_chain_segment
    from event_model import build_non_action_event
    from datetime import datetime, timezone, timedelta

    with tempfile.TemporaryDirectory() as tmpdir:
        chain_path = Path(tmpdir) / "chain.jsonl"
        archive_dir = Path(tmpdir) / "archive"
        stability_log = Path(tmpdir) / "stability.jsonl"
        meta_path = Path(tmpdir) / "chain_meta.json"

        # Create chain with old and new records
        old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        e1 = build_non_action_event("usage_attestation", {
            "attestation_type": "test", "attestation_scope": "unit",
        })
        e1["timestamp_utc"] = old_ts  # Make it old

        e2 = build_non_action_event("usage_attestation", {
            "attestation_type": "test", "attestation_scope": "unit",
        }, prev_record_hash=e1["record_hash"])

        with open(chain_path, "w") as fh:
            fh.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
            fh.write(json.dumps(e2, sort_keys=True, separators=(",", ":")) + "\n")

        meta_path.write_text(json.dumps({"chain_length": 2}))

        result = archive_chain_segment(
            chain_path, archive_dir,
            active_retention_days=90,
            stability_log_path=stability_log,
        )

        assert result is not None
        assert result["archived_count"] == 1
        assert result["kept_count"] == 1
        assert archive_dir.exists()
        assert len(list(archive_dir.glob("*.jsonl"))) == 1

        # Chain should have 1 record left
        with open(chain_path) as fh:
            remaining = [l for l in fh if l.strip()]
        assert len(remaining) == 1

        print("PASS: archive_chain_segment")


# ---------------------------------------------------------------------------
# Health signals collection
# ---------------------------------------------------------------------------

def test_collect_health_signals_structure():
    """collect_health_signals returns expected structure."""
    from chain_health import collect_health_signals

    with tempfile.TemporaryDirectory() as tmpdir:
        chain = Path(tmpdir) / "chain.jsonl"
        stability = Path(tmpdir) / "stability.jsonl"
        meta = Path(tmpdir) / "meta.json"
        chain.touch()

        result = collect_health_signals(chain, stability, meta, Path(tmpdir))

        assert "overall_status" in result
        assert "alerts" in result
        assert "chain" in result
        assert "deny_rate" in result
        assert "storage" in result
        assert "observations" in result
        assert "users" in result
        assert "license" in result
        assert "retention" in result
        assert result["overall_status"] == "healthy"
        print("PASS: collect_health_signals_structure")


def test_deny_rate_computation():
    """DENY rate is correctly computed from chain records."""
    from chain_health import _compute_deny_rate
    from event_model import build_non_action_event

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write some mock decision records
        for decision in ["ALLOW", "ALLOW", "DENY", "ALLOW", "DENY"]:
            rec = {"policy_decision": decision, "record_hash": "sha256:test", "timestamp_utc": "2026-03-31T12:00:00Z"}
            f.write(json.dumps(rec) + "\n")
        chain_path = Path(f.name)

    try:
        result = _compute_deny_rate(chain_path)
        assert result["deny_count"] == 2
        assert result["allow_count"] == 3
        assert result["total"] == 5
        assert abs(result["deny_rate"] - 0.4) < 0.01
        print("PASS: deny_rate_computation")
    finally:
        chain_path.unlink()


def test_chain_health_healthy_chain():
    """check_chain_health returns healthy for valid chain."""
    from chain_health import check_chain_health
    from event_model import build_non_action_event

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        e1 = build_non_action_event("usage_attestation", {
            "attestation_type": "test", "attestation_scope": "unit",
        })
        f.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
        chain_path = Path(f.name)

    try:
        result = check_chain_health(chain_path)
        assert result["status"] == "healthy"
        assert result["chain_event_count"] == 1
        assert result["break_info"] is None
        print("PASS: chain_health_healthy_chain")
    finally:
        chain_path.unlink()


def test_dashboard_health_page_registered():
    """app.js has Health tab and renderHealth function."""
    js = (REPO / "dashboard" / "ui" / "app.js").read_text()
    assert '"/health"' in js, "Missing /health route"
    assert "renderHealth" in js, "Missing renderHealth function"
    assert '"Health"' in js, "Missing Health tab label"
    print("PASS: dashboard_health_page_registered")


def test_dashboard_health_api_endpoint():
    """dashboard server.py has /api/health endpoint."""
    server_py = (REPO / "dashboard" / "server.py").read_text()
    assert '"/api/health"' in server_py, "Missing /api/health endpoint"
    assert "collect_health_signals" in server_py, "Missing health signals import"
    print("PASS: dashboard_health_api_endpoint")


def test_mcp_system_health_tool():
    """mcp/server.py has system_health tool."""
    import pytest
    pytest.skip("MCP broker archived (D-203) — test requires mcp server")


def test_health_alert_styles():
    """styles.css has health alert styling."""
    css = (REPO / "dashboard" / "ui" / "styles.css").read_text()
    assert ".health-alert" in css, "Missing health-alert class"
    assert ".health-alert--critical" in css, "Missing critical alert style"
    assert ".health-alert--attention" in css, "Missing attention alert style"
    print("PASS: health_alert_styles")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_classify_unsigned_legacy()
    test_classify_unknown_defaults_suspicious()
    test_classify_partial_write()
    test_auto_repair_known_truncate()
    test_auto_repair_refuses_suspicious()
    test_pattern_detection_below_threshold()
    test_pattern_detection_above_threshold()
    test_stability_log_append_and_read()
    test_stability_log_rejects_bad_type()
    test_archive_chain_segment()
    test_collect_health_signals_structure()
    test_deny_rate_computation()
    test_chain_health_healthy_chain()
    test_dashboard_health_page_registered()
    test_dashboard_health_api_endpoint()
    # test_mcp_system_health_tool — skipped (MCP broker archived D-203)
    test_health_alert_styles()
    test_check_chain_health_enumerates_two_breaks()
    test_check_chain_health_enumerates_three_breaks()
    test_check_chain_integrity_enumerates_three_breaks()
    print(f"\nAll 19 tests passed.")


# ---------------------------------------------------------------------------
# Multi-break enumeration tests (D-2026-0407-008)
# ---------------------------------------------------------------------------

def _build_chain_with_breaks(chain_path: Path, num_breaks: int) -> int:
    """Write a synthetic chain of 2*num_breaks+1 records, with `num_breaks`
    prev_record_hash mismatches sprinkled in. Returns the total record count.
    """
    from event_model import build_non_action_event

    records = []
    prev = None
    total = 2 * num_breaks + 1
    for i in range(total):
        rec = build_non_action_event(
            "usage_attestation",
            {"attestation_type": "test", "attestation_scope": f"unit{i}"},
            prev_record_hash=prev,
        )
        # Inject a break at every odd index (1, 3, 5...) up to num_breaks total.
        if i > 0 and (i % 2 == 1) and len([r for r in records if r.get("_broken")]) < num_breaks:
            rec["prev_record_hash"] = "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            # Recompute record_hash so verify_record_dict still passes for this rec.
            from event_model import _compute_event_record_hash  # type: ignore
            rec.pop("record_hash", None)
            rec["record_hash"] = _compute_event_record_hash(rec)
            rec["_broken"] = True
        records.append(rec)
        prev = rec["record_hash"]

    with open(chain_path, "w") as fh:
        for r in records:
            r_clean = {k: v for k, v in r.items() if k != "_broken"}
            fh.write(json.dumps(r_clean, sort_keys=True, separators=(",", ":")) + "\n")
    return total


def test_check_chain_health_enumerates_two_breaks():
    """check_chain_health collects all breaks, not just the first."""
    from chain_health import check_chain_health
    with tempfile.TemporaryDirectory() as tmpdir:
        chain_path = Path(tmpdir) / "chain.jsonl"
        total = _build_chain_with_breaks(chain_path, 2)
        result = check_chain_health(chain_path, Path(tmpdir) / "stability.jsonl", Path(tmpdir) / "chain_meta.json")
        assert result["chain_event_count"] == total
        assert result["break_count"] == 2, f"expected 2 breaks, got {result['break_count']}: {result.get('breaks')}"
        assert len(result["breaks"]) == 2
        assert all(b["reason"] == "prev_record_hash_mismatch" for b in result["breaks"])
        # Backward compat: break_info still populated with the first break.
        assert result["break_info"] is not None
        assert result["break_info"]["break_at_line"] == result["breaks"][0]["break_at_line"]
    print("PASS: check_chain_health_enumerates_two_breaks")


def test_check_chain_health_enumerates_three_breaks():
    from chain_health import check_chain_health
    with tempfile.TemporaryDirectory() as tmpdir:
        chain_path = Path(tmpdir) / "chain.jsonl"
        _build_chain_with_breaks(chain_path, 3)
        result = check_chain_health(chain_path, Path(tmpdir) / "stability.jsonl", Path(tmpdir) / "chain_meta.json")
        assert result["break_count"] == 3, f"expected 3 breaks, got {result['break_count']}: {result.get('breaks')}"
        assert len(result["breaks"]) == 3
    print("PASS: check_chain_health_enumerates_three_breaks")


def test_check_chain_integrity_enumerates_three_breaks():
    """check_chain_integrity also enumerates all breaks and preserves backward compat."""
    from readout import check_chain_integrity
    with tempfile.TemporaryDirectory() as tmpdir:
        chain_path = Path(tmpdir) / "chain.jsonl"
        _build_chain_with_breaks(chain_path, 3)
        result = check_chain_integrity(chain_path)
        assert result["status"] == "broken"
        assert result["break_count"] == 3, f"expected 3 breaks, got {result['break_count']}: {result.get('breaks')}"
        # Backward compat: broken_at and reason populated with first break.
        assert result["broken_at"] == result["breaks"][0]["broken_at"]
        assert result["reason"] == result["breaks"][0]["reason"]
    print("PASS: check_chain_integrity_enumerates_three_breaks")
