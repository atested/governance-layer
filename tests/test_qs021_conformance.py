import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard"))
sys.path.insert(0, str(REPO / "scripts"))

from conformance import DashboardQAChainReader, build_conformance_payload
from qa_chain_fixtures import write_fixture


_dashboard_spec = importlib.util.spec_from_file_location(
    "dashboard_server_qs021", REPO / "dashboard" / "server.py"
)
ds = importlib.util.module_from_spec(_dashboard_spec)
assert _dashboard_spec.loader is not None
_dashboard_spec.loader.exec_module(ds)


POLICY_HASH = "sha256:" + "a" * 64
CAP_HASH = "sha256:" + "b" * 64


def _write(path: Path, fixture: str) -> Path:
    return write_fixture(
        path,
        fixture,
        policy_rules_hash=POLICY_HASH,
        capability_registry_hash=CAP_HASH,
    )


def test_conformance_verified_with_healthy_qa_chain(tmp_path):
    qa_chain = _write(tmp_path / "qa-chain.jsonl", "healthy")
    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "verified"
    assert payload["quality_service_alive"] is True
    assert payload["qa_chain_present"] is True
    assert payload["modes"]["environmental"]["status"] == "healthy"
    assert payload["modes"]["post_hoc"]["status"] == "not_active"
    assert payload["modes"]["spc"]["status"] == "not_active"
    assert payload["latest_snapshot"]["sequence"] == 1


def test_conformance_intervention_with_condition_fixture(tmp_path):
    qa_chain = _write(tmp_path / "qa-chain.jsonl", "condition")
    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "intervention"
    assert payload["modes"]["environmental"]["status"] == "condition_detected"
    assert payload["active_conditions"][0]["condition_id"] == "CR-CRIT-001"
    assert payload["active_conditions"][0]["condition_type"] == "stale_rules"
    assert "Restart the proxy" in payload["active_conditions"][0]["guidance"]


def test_conformance_halted_with_absent_qa_chain(tmp_path):
    qa_chain = tmp_path / "missing-qa-chain.jsonl"
    payload = build_conformance_payload(DashboardQAChainReader(qa_chain))

    assert payload["state"] == "halted"
    assert payload["quality_service_alive"] is False
    assert payload["qa_chain_present"] is False
    assert "does not exist" in payload["detail"]


def test_conformance_halted_when_sequence_stale(tmp_path, monkeypatch):
    import conformance

    qa_chain = _write(tmp_path / "qa-chain.jsonl", "healthy")
    reader = DashboardQAChainReader(qa_chain)
    monkeypatch.setenv("ATESTED_CONFORMANCE_STALE_SECONDS", "0.5")
    monkeypatch.setattr(conformance.time, "monotonic", lambda: 1000.0)
    first = build_conformance_payload(reader)
    assert first["state"] == "verified"

    monkeypatch.setattr(conformance.time, "monotonic", lambda: 1001.0)
    second = build_conformance_payload(reader)
    assert second["state"] == "halted"
    assert second["detail"] == "QA chain snapshot sequence not advancing"


def test_dashboard_conformance_snapshot_uses_configured_reader(tmp_path, monkeypatch):
    qa_chain = _write(tmp_path / "qa-chain.jsonl", "condition")
    monkeypatch.setattr(ds, "QA_CHAIN", qa_chain)
    monkeypatch.setattr(ds, "_conformance_reader", None)

    payload = ds._conformance_state_snapshot()

    assert payload["state"] == "intervention"
    assert payload["latest_snapshot"]["policy_rules_hash"] == POLICY_HASH


class _DummyHandler:
    def __init__(self):
        self.status = None
        self.headers = []
        self.wfile = BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers.append((key, value))

    def end_headers(self):
        pass

    def _cors_origin(self):
        return ""


def test_conformance_api_route_returns_payload(tmp_path, monkeypatch):
    qa_chain = _write(tmp_path / "qa-chain.jsonl", "healthy")
    monkeypatch.setattr(ds, "QA_CHAIN", qa_chain)
    monkeypatch.setattr(ds, "_conformance_reader", None)
    handler = _DummyHandler()

    ds.DashboardHandler._handle_api(handler, urlparse("/api/conformance"))
    payload = json.loads(handler.wfile.getvalue().decode("utf-8"))

    assert handler.status == 200
    assert payload["state"] == "verified"
    assert payload["modes"]["environmental"]["status"] == "healthy"
    assert payload["modes"]["post_hoc"]["status"] == "not_active"


def test_ui_indicator_is_present():
    server_source = (REPO / "dashboard" / "server.py").read_text(encoding="utf-8")
    api_source = (REPO / "dashboard" / "ui-next" / "api.js").read_text(encoding="utf-8")
    main_source = (REPO / "dashboard" / "ui-next" / "main-page.js").read_text(encoding="utf-8")

    assert '"/api/conformance"' in server_source
    assert "getConformance" in api_source
    assert "mp-conformance-indicator" in main_source
    assert "mp-conformance-panel" in main_source
    assert "Mode 3 not yet implemented" in main_source or "Future modes" in main_source
