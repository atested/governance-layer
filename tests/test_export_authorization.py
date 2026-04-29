import json
import sys
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "mcp"))

spec = importlib.util.spec_from_file_location(
    "dashboard_server_under_test",
    REPO / "dashboard" / "server.py",
)
dashboard_server = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dashboard_server)


def test_export_token_is_scoped_and_expires(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
    token_data = dashboard_server._issue_export_token({
        "surface": "audit",
        "format": "json",
    })

    assert dashboard_server._validate_export_token(token_data["token"], surface="audit") is not None
    assert dashboard_server._validate_export_token(token_data["token"], surface="activity") is None

    monkeypatch.setattr(
        dashboard_server._time_mod,
        "time",
        lambda: now + dashboard_server.EXPORT_TOKEN_TTL_SECONDS + 1,
    )
    assert dashboard_server._validate_export_token(token_data["token"], surface="audit") is None


def test_export_event_records_archive_reference_in_live_chain(tmp_path, monkeypatch):
    chain_path = tmp_path / "decision-chain.jsonl"
    monkeypatch.setattr(dashboard_server, "CHAIN", chain_path)

    event = dashboard_server._record_export_event({
        "export_level": "raw",
        "surface": "audit",
        "format": "json",
        "operator_identity": "license_sha256:test",
        "chain_source": "archive",
        "archive_id": "chain-archive-test",
        "archive_manifest_path": str(tmp_path / "archive" / "chain-archive-test.manifest.json"),
        "record_count": 3,
        "filters": {"policy_decision": "DENY"},
        "password_recorded": False,
    })

    stored = json.loads(chain_path.read_text(encoding="utf-8").strip())
    assert event["event_type"] == "chain_export_created"
    assert stored["event_type"] == "chain_export_created"
    assert stored["chain_source"] == "archive"
    assert stored["archive_id"] == "chain-archive-test"
    assert stored["archive_manifest_path"].endswith("chain-archive-test.manifest.json")
    assert stored["record_count"] == 3


# ---------------------------------------------------------------------------
# SEC-2026-002: Export token scope binding
# ---------------------------------------------------------------------------


def test_token_scope_rejects_wider_range(monkeypatch):
    """A token authorized for range 1-10 cannot export range 1-100."""
    now = 1000.0
    monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
    token_data = dashboard_server._issue_export_token({
        "surface": "audit",
        "chain_source": "live",
        "range_start_sequence": 1,
        "range_end_sequence": 10,
    })
    token = token_data["token"]

    # Exact scope match succeeds
    assert dashboard_server._validate_export_token(
        token, surface="audit", chain_source="live",
        start_sequence=1, end_sequence=10,
    ) is not None

    # Wider range fails
    assert dashboard_server._validate_export_token(
        token, surface="audit", chain_source="live",
        start_sequence=1, end_sequence=100,
    ) is None

    # Earlier start fails
    assert dashboard_server._validate_export_token(
        token, surface="audit", chain_source="live",
        start_sequence=0, end_sequence=10,
    ) is None


def test_token_scope_rejects_different_chain_source(monkeypatch):
    """A token authorized for live chain cannot export an archive."""
    now = 1000.0
    monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
    token_data = dashboard_server._issue_export_token({
        "surface": "audit",
        "chain_source": "live",
        "archive_id": "",
        "range_start_sequence": 1,
        "range_end_sequence": 10,
    })
    token = token_data["token"]

    assert dashboard_server._validate_export_token(
        token, surface="audit", chain_source="archive",
        archive_id="arch-123",
    ) is None


def test_token_scope_allows_subset_range(monkeypatch):
    """A token authorized for range 1-100 allows a subset range 5-50."""
    now = 1000.0
    monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
    token_data = dashboard_server._issue_export_token({
        "surface": "audit",
        "chain_source": "live",
        "range_start_sequence": 1,
        "range_end_sequence": 100,
    })
    token = token_data["token"]

    assert dashboard_server._validate_export_token(
        token, surface="audit", chain_source="live",
        start_sequence=5, end_sequence=50,
    ) is not None
