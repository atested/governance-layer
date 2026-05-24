"""Tests for QS-024 legacy health-surface deprecation.

Legacy endpoints continue to function but must:
  1. Set the Deprecation: true HTTP header.
  2. Set a Link: <successor>; rel="successor-version" header.
  3. Include {deprecated: true, successor: "/api/conformance"} in the JSON body.
  4. Direct operators to /api/conformance.

Deprecation, not removal: existing clients keep working.
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dashboard"))
sys.path.insert(0, str(REPO / "scripts"))

import server as ds  # noqa: E402


class _DummyHandler:
    """Minimal HTTP handler stand-in matching the patterns in test_qs021."""

    def __init__(self):
        self.status = None
        self.headers: list[tuple[str, str]] = []
        self.wfile = BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers.append((key, value))

    def end_headers(self):
        pass

    def _cors_origin(self):
        return ""


def _headers_dict(handler):
    """HTTP headers are case-insensitive in HTTP/1.x; lowercase the keys."""
    return {key.lower(): value for key, value in handler.headers}


# ---------------------------------------------------------------------------
# _deprecated_json_response helper
# ---------------------------------------------------------------------------


def test_deprecated_json_response_helper_sets_headers():
    handler = _DummyHandler()
    ds._deprecated_json_response(handler, {"ok": True})
    headers = _headers_dict(handler)
    assert headers.get("deprecation") == "true"
    assert "successor-version" in headers.get("link", "")
    assert "/api/conformance" in headers.get("link", "")


def test_deprecated_json_response_helper_augments_body():
    handler = _DummyHandler()
    ds._deprecated_json_response(handler, {"ok": True, "chain_status": "healthy"})
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert body["deprecated"] is True
    assert body["successor"] == "/api/conformance"
    # Original payload preserved
    assert body["ok"] is True
    assert body["chain_status"] == "healthy"


def test_deprecated_json_response_non_dict_payload():
    """If the payload isn't a dict, it is wrapped under 'data' with deprecation metadata."""
    handler = _DummyHandler()
    ds._deprecated_json_response(handler, "scalar value")
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert body["deprecated"] is True
    assert body["successor"] == "/api/conformance"


def test_deprecated_json_response_preserves_status_code():
    handler = _DummyHandler()
    ds._deprecated_json_response(handler, {"error": "use POST"}, 405)
    assert handler.status == 405
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert body["error"] == "use POST"
    assert body["deprecated"] is True


# ---------------------------------------------------------------------------
# /api/status — legacy
# ---------------------------------------------------------------------------


def test_legacy_status_marks_deprecated(monkeypatch, tmp_path):
    """The /api/status endpoint must mark itself deprecated."""
    # Stub out the heavy dependencies of assemble_governance_status_record.
    monkeypatch.setattr(ds, "CHAIN", tmp_path / "decision-chain.jsonl")
    monkeypatch.setattr(ds, "_get_verification_tracker", lambda: None)
    monkeypatch.setattr(ds, "_get_approval_store", lambda: None)
    monkeypatch.setattr(ds, "_machine_status_snapshot", lambda: {"role": "primary"})

    def _stub_assemble(*args, **kwargs):
        return {"chain_health": "healthy"}

    import readout  # noqa: F401
    monkeypatch.setattr(
        "readout.assemble_governance_status_record", _stub_assemble
    )

    handler = _DummyHandler()
    ds.DashboardHandler._handle_api(handler, urlparse("/api/status"))
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    headers = _headers_dict(handler)

    assert handler.status == 200
    assert body["deprecated"] is True
    assert body["successor"] == "/api/conformance"
    assert body["chain_health"] == "healthy"
    assert headers.get("deprecation") == "true"


# ---------------------------------------------------------------------------
# /api/health — legacy
# ---------------------------------------------------------------------------


def test_legacy_health_marks_deprecated(monkeypatch, tmp_path):
    """The /api/health endpoint must mark itself deprecated."""
    monkeypatch.setattr(ds, "CHAIN", tmp_path / "decision-chain.jsonl")
    monkeypatch.setattr(ds, "RUNTIME", tmp_path)
    monkeypatch.setattr(ds, "_machine_status_snapshot", lambda: {"role": "primary"})
    monkeypatch.setattr(ds, "_maybe_trigger_archive", lambda: None)

    def _stub_collect(chain_path, *args, **kwargs):
        return {"chain": {"status": "healthy", "chain_event_count": 0}}

    monkeypatch.setattr("chain_health.collect_health_signals", _stub_collect)

    handler = _DummyHandler()
    ds.DashboardHandler._handle_api(handler, urlparse("/api/health"))
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    headers = _headers_dict(handler)

    assert handler.status == 200
    assert body["deprecated"] is True
    assert body["successor"] == "/api/conformance"
    assert headers.get("deprecation") == "true"
    assert "/api/conformance" in headers.get("link", "")


# ---------------------------------------------------------------------------
# /api/health/acknowledge — legacy
# ---------------------------------------------------------------------------


def test_legacy_health_acknowledge_get_marks_deprecated(monkeypatch, tmp_path):
    """GET /api/health/acknowledge (POST-only) returns deprecated 405."""
    handler = _DummyHandler()
    ds.DashboardHandler._handle_api(handler, urlparse("/api/health/acknowledge"))
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    headers = _headers_dict(handler)

    assert handler.status == 405
    assert body["deprecated"] is True
    assert body["successor"] == "/api/conformance"
    assert headers.get("deprecation") == "true"


# ---------------------------------------------------------------------------
# Endpoint continues to function (deprecation, not removal)
# ---------------------------------------------------------------------------


def test_legacy_health_still_returns_data(monkeypatch, tmp_path):
    """Deprecation must not remove functionality. Legacy clients still work."""
    monkeypatch.setattr(ds, "CHAIN", tmp_path / "decision-chain.jsonl")
    monkeypatch.setattr(ds, "RUNTIME", tmp_path)
    monkeypatch.setattr(ds, "_machine_status_snapshot", lambda: {"role": "primary"})
    monkeypatch.setattr(ds, "_maybe_trigger_archive", lambda: None)

    def _stub_collect(chain_path, *args, **kwargs):
        return {"chain": {"status": "healthy"}}

    monkeypatch.setattr("chain_health.collect_health_signals", _stub_collect)

    handler = _DummyHandler()
    ds.DashboardHandler._handle_api(handler, urlparse("/api/health"))
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    # The underlying health data must still be present — deprecation overlays,
    # it does not replace.
    assert "chain" in body
    assert body["machine"]["role"] == "primary"


# ---------------------------------------------------------------------------
# Conformance endpoint is NOT deprecated
# ---------------------------------------------------------------------------


def test_conformance_endpoint_not_deprecated(monkeypatch, tmp_path):
    """The successor endpoint must NOT carry deprecation headers."""
    qa_chain = tmp_path / "qa-chain.jsonl"
    qa_chain.write_text("", encoding="utf-8")
    monkeypatch.setattr(ds, "QA_CHAIN", qa_chain)
    monkeypatch.setattr(ds, "_conformance_reader", None)

    handler = _DummyHandler()
    ds.DashboardHandler._handle_api(handler, urlparse("/api/conformance"))
    body = json.loads(handler.wfile.getvalue().decode("utf-8"))
    headers = _headers_dict(handler)

    assert handler.status == 200
    assert body.get("deprecated") is not True
    assert "deprecation" not in headers
