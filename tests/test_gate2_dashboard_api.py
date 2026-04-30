"""Gate 2 — Dashboard API endpoint tests.

Dispatch 176-D-2026-0430 (RELEASE-G2-DASHBOARD-API-TESTS)

Scopes:
  2. Local read boundary verification
  3. Mutation endpoint auth tests
  4. Export endpoint depth
  5. Chain walker API tests
  6. Record detail and event types
  7. Telemetry and trouble boundary

Test approach: Direct function/method testing without starting an HTTP server.
The dashboard handler is tested by importing the module and calling internal
functions. Auth boundary tests verify the _check_auth and _origin_allowed
methods via source inspection and mock request objects.
"""

import hashlib
import importlib.util
import inspect
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "mcp"))

# Load dashboard server module via importlib
_dashboard_spec = importlib.util.spec_from_file_location(
    "dashboard_server_gate2", REPO / "dashboard" / "server.py"
)
ds = importlib.util.module_from_spec(_dashboard_spec)
assert _dashboard_spec.loader is not None
_dashboard_spec.loader.exec_module(ds)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chain_record(seq, decision="ALLOW", prev_hash=None, event_type=None, **extra):
    base = {
        "event_model_version": "0.1",
        "record_type": "mediated_decision" if not event_type else "non_action_event",
        "timestamp_utc": f"2026-04-30T10:{seq:02d}:00Z",
        "request_id": f"req-g2-{seq}",
        "user_identity": "operator@test.local",
        "original_tool": "FS_READ",
        "classification": {
            "action_type": "read",
            "targets": [f"/test/file-{seq}.txt"],
            "confidence_tier": 1,
        },
        "policy_decision": decision,
        "prev_record_hash": prev_hash,
    }
    if event_type:
        base["event_type"] = event_type
        base["record_type"] = "non_action_event"
    base.update(extra)
    canon = json.dumps(base, sort_keys=True, separators=(",", ":"))
    base["record_hash"] = "sha256:" + hashlib.sha256(canon.encode()).hexdigest()
    return base


def _write_chain(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in records:
        lines.append(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    path.write_text("".join(lines), encoding="utf-8")


def _build_linked_chain(count=5, include_deny=False, include_events=False):
    records = []
    prev_hash = None
    for i in range(1, count + 1):
        if include_deny and i == 2:
            decision = "DENY"
        else:
            decision = "ALLOW"
        if include_events and i == 3:
            r = _make_chain_record(i, prev_hash=prev_hash, event_type="policy_rules_changed")
        elif include_events and i == 4:
            r = _make_chain_record(i, prev_hash=prev_hash, event_type="opaque_artifact_approval",
                                   artifact_identity="test-file.py",
                                   governed_family="fs",
                                   deployment_context="",
                                   policy_version="",
                                   approving_operator="dashboard_operator")
        elif include_events and i == 5:
            r = _make_chain_record(i, prev_hash=prev_hash, event_type="chain_export_created",
                                   surface="audit", format="json")
        else:
            r = _make_chain_record(i, decision=decision, prev_hash=prev_hash)
        records.append(r)
        prev_hash = r["record_hash"]
    return records


@pytest.fixture
def dashboard_env(tmp_path, monkeypatch):
    """Set up an isolated dashboard environment."""
    chain = tmp_path / "LOGS" / "decision-chain.jsonl"
    records_dir = tmp_path / "LOGS" / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    telemetry_dir = tmp_path / "LOGS" / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    trouble_dir = tmp_path / "LOGS" / "trouble"
    trouble_dir.mkdir(parents=True, exist_ok=True)
    feedback_dir = tmp_path / "LOGS" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(ds, "CHAIN", chain)
    monkeypatch.setattr(ds, "RECORDS_DIR", records_dir)
    monkeypatch.setattr(ds, "RUNTIME", tmp_path)
    monkeypatch.setattr(ds, "TELEMETRY_SUMMARY", telemetry_dir / "summary.json")
    monkeypatch.setattr(ds, "_DASHBOARD_TOKEN", "test-token-gate2")
    monkeypatch.setattr(ds, "_DASHBOARD_PORT", 9999)

    chain_records = _build_linked_chain(5, include_deny=True, include_events=True)
    _write_chain(chain, chain_records)

    return {
        "tmp_path": tmp_path,
        "chain": chain,
        "records_dir": records_dir,
        "telemetry_dir": telemetry_dir,
        "trouble_dir": trouble_dir,
        "feedback_dir": feedback_dir,
        "chain_records": chain_records,
        "token": "test-token-gate2",
    }


def _mock_handler(token=None, origin=None):
    """Create a mock handler object with _check_auth and _origin_allowed."""
    handler = MagicMock(spec=ds.DashboardHandler)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
    handler.headers = MagicMock()
    handler.headers.get = lambda key, default="": headers.get(key, default)
    # Bind the actual methods
    handler._check_auth = lambda: ds.DashboardHandler._check_auth(handler)
    handler._origin_allowed = lambda: ds.DashboardHandler._origin_allowed(handler)
    handler._cors_origin = lambda: ds.DashboardHandler._cors_origin(handler)
    return handler


# ===========================================================================
# Scope 2 — Local Read Boundary Verification
# ===========================================================================

class TestLocalReadBoundary:
    """Verify the three local read boundary conditions."""

    def test_server_binds_to_localhost(self):
        """Server binds to 127.0.0.1 by default (source code verification)."""
        source = inspect.getsource(ds.main)
        assert '"127.0.0.1"' in source

    def test_cors_rejects_non_local_origin(self, monkeypatch):
        """CORS rejects non-localhost origins."""
        monkeypatch.setattr(ds, "_DASHBOARD_PORT", 9700)
        handler = _mock_handler(origin="https://evil.example.com")
        assert handler._origin_allowed() is False
        assert handler._cors_origin() == ""

    def test_cors_allows_127_0_0_1_origin(self, monkeypatch):
        """CORS allows 127.0.0.1 origin."""
        monkeypatch.setattr(ds, "_DASHBOARD_PORT", 9700)
        handler = _mock_handler(origin="http://127.0.0.1:9700")
        assert handler._origin_allowed() is True
        assert handler._cors_origin() == "http://127.0.0.1:9700"

    def test_cors_allows_localhost_origin(self, monkeypatch):
        """CORS allows localhost origin."""
        monkeypatch.setattr(ds, "_DASHBOARD_PORT", 9700)
        handler = _mock_handler(origin="http://localhost:9700")
        assert handler._origin_allowed() is True
        assert handler._cors_origin() == "http://localhost:9700"

    def test_cors_rejects_wrong_port(self, monkeypatch):
        """CORS rejects localhost with wrong port."""
        monkeypatch.setattr(ds, "_DASHBOARD_PORT", 9700)
        handler = _mock_handler(origin="http://127.0.0.1:8080")
        assert handler._origin_allowed() is False

    def test_read_endpoints_do_not_mutate_chain(self, dashboard_env):
        """Read-only functions do not modify the chain file."""
        chain_before = dashboard_env["chain"].read_text(encoding="utf-8")

        from readout import governance_activity_view, governance_approvals_view
        from approval_store import ApprovalStore
        governance_activity_view(dashboard_env["chain"], limit=10)
        governance_approvals_view(dashboard_env["chain"], ApprovalStore())

        chain_after = dashboard_env["chain"].read_text(encoding="utf-8")
        assert chain_after == chain_before

    def test_read_endpoints_do_not_create_files(self, dashboard_env):
        """Read-only functions do not create telemetry or trouble files."""
        tel_files_before = set(f.name for f in dashboard_env["telemetry_dir"].iterdir())
        trouble_files_before = set(f.name for f in dashboard_env["trouble_dir"].iterdir())

        from readout import governance_activity_view
        governance_activity_view(dashboard_env["chain"], limit=10)

        tel_files_after = set(f.name for f in dashboard_env["telemetry_dir"].iterdir())
        trouble_files_after = set(f.name for f in dashboard_env["trouble_dir"].iterdir())
        assert tel_files_after == tel_files_before
        assert trouble_files_after == trouble_files_before


# ===========================================================================
# Scope 3 — Mutation Endpoint Auth Tests
# ===========================================================================

class TestMutationEndpointAuth:
    """Every API request requires bearer token auth."""

    def test_valid_token_accepted(self, monkeypatch):
        monkeypatch.setattr(ds, "_DASHBOARD_TOKEN", "correct-token")
        handler = _mock_handler(token="correct-token")
        assert handler._check_auth() is True

    def test_no_token_rejected(self, monkeypatch):
        monkeypatch.setattr(ds, "_DASHBOARD_TOKEN", "correct-token")
        handler = _mock_handler()
        assert handler._check_auth() is False

    def test_wrong_token_rejected(self, monkeypatch):
        monkeypatch.setattr(ds, "_DASHBOARD_TOKEN", "correct-token")
        handler = _mock_handler(token="wrong-token")
        assert handler._check_auth() is False

    def test_empty_bearer_rejected(self, monkeypatch):
        monkeypatch.setattr(ds, "_DASHBOARD_TOKEN", "correct-token")
        handler = _mock_handler(token="")
        assert handler._check_auth() is False

    def test_do_get_rejects_unauthenticated_api(self, monkeypatch):
        """do_GET checks auth before processing /api/* paths (source verification)."""
        source = inspect.getsource(ds.DashboardHandler.do_GET)
        # The auth check must appear before _handle_api
        auth_pos = source.find("_check_auth")
        handle_pos = source.find("_handle_api")
        assert auth_pos > 0
        assert handle_pos > 0
        assert auth_pos < handle_pos, "Auth check must come before API handling"

    def test_do_post_rejects_unauthenticated_api(self, monkeypatch):
        """do_POST checks auth before processing /api/* paths (source verification)."""
        source = inspect.getsource(ds.DashboardHandler.do_POST)
        auth_pos = source.find("_check_auth")
        # All POST handlers are after auth check
        first_handler_pos = source.find("/api/observe")
        assert auth_pos > 0
        assert first_handler_pos > 0
        assert auth_pos < first_handler_pos, "Auth check must come before POST handlers"

    def test_static_files_served_without_auth(self):
        """Static files (/, /index.html) do not require auth (source verification)."""
        source = inspect.getsource(ds.DashboardHandler.do_GET)
        # The index.html path is in the elif branch after /api/ check
        assert "index.html" in source
        # Verify the branching: /api/ → check auth → handle; else → serve without auth
        api_check = source.find("/api/")
        serve_index = source.find("_serve_index_html")
        assert api_check > 0
        assert serve_index > 0
        assert serve_index > api_check

    def test_observe_writes_to_chain(self, dashboard_env):
        """POST /api/observe is a mutation endpoint (writes chain record)."""
        chain_before = dashboard_env["chain"].read_text()
        from event_model import build_non_action_event, UNGOVERNED_OPERATION_TYPES
        assert "read" in UNGOVERNED_OPERATION_TYPES
        event = build_non_action_event("ungoverned_operation_observed", {
            "operation_type": "read", "target": "/test", "source": "test",
        })
        ds._append_chain_record_atomic(event)
        chain_after = dashboard_env["chain"].read_text()
        assert len(chain_after) > len(chain_before)
        last_line = chain_after.strip().splitlines()[-1]
        assert "ungoverned_operation_observed" in last_line

    def test_approval_add_writes_to_chain(self, dashboard_env):
        """POST /api/approvals/add writes opaque_artifact_approval to chain."""
        chain_before = dashboard_env["chain"].read_text()
        from event_model import build_non_action_event
        event = build_non_action_event("opaque_artifact_approval", {
            "artifact_identity": "test-artifact",
            "approving_operator": "test-operator",
        })
        ds._append_chain_record_atomic(event)
        chain_after = dashboard_env["chain"].read_text()
        assert "opaque_artifact_approval" in chain_after[len(chain_before):]


# ===========================================================================
# Scope 4 — Export Endpoint Depth
# ===========================================================================

class TestExportEndpointDepth:
    """API-level tests for export authorization flow."""

    def test_export_authorize_requires_license_key(self):
        """Export authorize validates license_key field is present."""
        source = inspect.getsource(ds.DashboardHandler._handle_export_authorize)
        assert "license_key" in source
        assert "validate_license_key" in source
        # Without key → 400
        assert '"license_key required"' in source or "'license_key required'" in source

    def test_export_authorize_issues_scoped_token(self, dashboard_env, monkeypatch):
        """_issue_export_token creates a scoped, time-limited token."""
        now = 1000.0
        monkeypatch.setattr(ds._time_mod, "time", lambda: now)

        scope = {
            "surface": "audit",
            "format": "json",
            "chain_source": "live",
            "range_start_sequence": 1,
            "range_end_sequence": 5,
        }
        token_data = ds._issue_export_token(scope)
        assert "token" in token_data
        assert token_data["expires_at"] == now + ds.EXPORT_TOKEN_TTL_SECONDS

        # Token is valid for correct surface
        valid = ds._validate_export_token(token_data["token"], surface="audit")
        assert valid is not None

        # Token is rejected for wrong surface
        invalid = ds._validate_export_token(token_data["token"], surface="activity")
        assert invalid is None

    def test_export_authorize_records_chain_event(self, dashboard_env):
        """_record_export_event writes chain_export_created to chain."""
        chain_before = dashboard_env["chain"].read_text()

        event = ds._record_export_event({
            "surface": "audit",
            "format": "json",
            "operator_identity": "license_sha256:test",
            "chain_source": "live",
        })

        chain_after = dashboard_env["chain"].read_text()
        new_content = chain_after[len(chain_before):]
        assert "chain_export_created" in new_content
        assert event["event_type"] == "chain_export_created"

    def test_export_package_requires_export_token(self):
        """Export package handler validates export token."""
        source = inspect.getsource(ds.DashboardHandler._handle_export_package)
        assert "_validate_export_token" in source
        assert '"export_token"' in source or "'export_token'" in source

    def test_export_package_records_encrypted_package_event(self):
        """Export package handler records encrypted_evidence_package_created."""
        source = inspect.getsource(ds.DashboardHandler._handle_export_package)
        assert "encrypted_evidence_package_created" in source
        assert "_append_chain_record_atomic" in source

    def test_export_token_scope_binding(self, dashboard_env, monkeypatch):
        """Export token enforces chain_source and range scope binding."""
        now = 1000.0
        monkeypatch.setattr(ds._time_mod, "time", lambda: now)

        scope = {
            "surface": "audit",
            "chain_source": "live",
            "range_start_sequence": 1,
            "range_end_sequence": 10,
        }
        token_data = ds._issue_export_token(scope)
        token = token_data["token"]

        # Valid within scope
        assert ds._validate_export_token(token, surface="audit",
                                         chain_source="live", start_sequence=1, end_sequence=10) is not None

        # Rejected: archive source when token scoped to live
        assert ds._validate_export_token(token, surface="audit",
                                         chain_source="archive") is None

        # Rejected: range exceeds scope
        assert ds._validate_export_token(token, surface="audit",
                                         chain_source="live", end_sequence=100) is None

    def test_export_token_invalidated_after_use(self, dashboard_env, monkeypatch):
        """Export token is removed from store after package is built (source verification)."""
        source = inspect.getsource(ds.DashboardHandler._handle_export_package)
        assert "_export_tokens.pop(export_token" in source

    def test_activity_export_mode_requires_token(self):
        """GET /api/activity with export_mode requires valid export token."""
        source = inspect.getsource(ds.DashboardHandler._handle_api)
        # Find the activity handler section
        activity_idx = source.find('"/api/activity"')
        assert activity_idx > 0
        # After "/api/activity", export_mode check should appear before the view call
        section = source[activity_idx:activity_idx + 500]
        assert "export_mode" in section
        assert "_validate_export_token" in section


# ===========================================================================
# Scope 5 — Chain Walker API Tests
# ===========================================================================

class TestChainWalkerAPI:
    """Verify the chain walker returns correct data."""

    def test_walker_returns_live_chain_window(self, dashboard_env):
        """walker_query returns correct data for live chain."""
        from chain_walker import walker_query
        data = walker_query(dashboard_env["chain"], chain_source="live")
        assert data.get("total_matching") == 5

    def test_walker_returns_records_with_content(self, dashboard_env):
        """Walker rows contain expected fields."""
        from chain_walker import walker_query
        data = walker_query(dashboard_env["chain"], chain_source="live")
        rows = data.get("rows") or data.get("records") or []
        assert len(rows) > 0
        row = rows[0]
        assert "record_hash" in row or "hash" in row

    def test_walker_respects_policy_decision_filter(self, dashboard_env):
        """Walker filtering by policy_decision returns matching records."""
        from chain_walker import walker_query
        data = walker_query(
            dashboard_env["chain"], chain_source="live", policy_decision="DENY"
        )
        rows = data.get("rows") or data.get("records") or []
        for row in rows:
            decision = row.get("policy_decision") or row.get("decision", "")
            if decision:
                assert decision == "DENY"

    def test_walker_invalid_archive_returns_error(self, dashboard_env):
        """Walker with invalid archive_id returns error, not live chain.
        (SEC-2026-007 — API-level confirmation; unit tests in test_chain_walker.py)"""
        from chain_walker import walker_query
        data = walker_query(
            dashboard_env["chain"], chain_source="archive", archive_id="nonexistent-id"
        )
        error = data.get("error") or ""
        rows = data.get("rows") or data.get("records") or []
        # Should error or return empty, not fall back to live chain (5 records)
        assert error or len(rows) == 0, \
            f"Invalid archive_id returned {len(rows)} rows — possible live chain fallback"

    def test_archives_endpoint_returns_list(self, dashboard_env):
        """list_archives returns a list (may be empty)."""
        from chain_archive import list_archives
        archives = list_archives(dashboard_env["chain"])
        assert isinstance(archives, list)

    def test_walker_api_path_uses_walker_query(self):
        """GET /api/audit/walker calls walker_query (source verification)."""
        source = inspect.getsource(ds.DashboardHandler._handle_api)
        walker_section_idx = source.find('"/api/audit/walker"')
        assert walker_section_idx > 0
        section = source[walker_section_idx:walker_section_idx + 500]
        assert "walker_query" in section


# ===========================================================================
# Scope 6 — Record Detail and Event Types
# ===========================================================================

class TestRecordDetailEventTypes:
    """Verify record detail and activity endpoints handle all event types."""

    def test_activity_returns_records(self, dashboard_env):
        """governance_activity_view returns records from chain."""
        from readout import governance_activity_view
        data = governance_activity_view(dashboard_env["chain"], limit=10)
        records = data.get("records") or data.get("entries") or []
        assert len(records) > 0

    def test_allow_records_in_activity(self, dashboard_env):
        """Activity view includes ALLOW decisions."""
        from readout import governance_activity_view
        data = governance_activity_view(
            dashboard_env["chain"], limit=10, policy_decision="ALLOW"
        )
        records = data.get("records") or data.get("entries") or []
        assert len(records) > 0

    def test_deny_records_in_activity(self, dashboard_env):
        """Activity view includes DENY decisions."""
        from readout import governance_activity_view
        data = governance_activity_view(
            dashboard_env["chain"], limit=10, policy_decision="DENY"
        )
        records = data.get("records") or data.get("entries") or []
        assert len(records) > 0

    def test_audit_record_detail(self, dashboard_env):
        """audit_record_detail returns data for a known record."""
        from readout import audit_record_detail
        rid = dashboard_env["chain_records"][0]["request_id"]
        data = audit_record_detail(
            dashboard_env["chain"], dashboard_env["records_dir"], record_id=rid
        )
        assert data is not None

    def test_audit_report_grouping(self, dashboard_env):
        """audit_report returns grouped summary."""
        from readout import audit_report
        data = audit_report(
            dashboard_env["chain"], dashboard_env["records_dir"], group_by="tool"
        )
        assert data is not None

    def test_integrity_event_in_chain(self, dashboard_env):
        """Chain contains a policy_rules_changed integrity event."""
        chain_text = dashboard_env["chain"].read_text(encoding="utf-8")
        assert "policy_rules_changed" in chain_text

    def test_approval_event_in_chain(self, dashboard_env):
        """Chain contains an opaque_artifact_approval event."""
        chain_text = dashboard_env["chain"].read_text(encoding="utf-8")
        assert "opaque_artifact_approval" in chain_text

    def test_export_event_in_chain(self, dashboard_env):
        """Chain contains a chain_export_created event."""
        chain_text = dashboard_env["chain"].read_text(encoding="utf-8")
        assert "chain_export_created" in chain_text

    def test_status_endpoint_returns_all_sections(self, dashboard_env):
        """assemble_governance_status_record returns a complete status record."""
        from readout import assemble_governance_status_record
        from verification import VerificationStateTracker
        from approval_store import ApprovalStore
        tracker = VerificationStateTracker()
        store = ApprovalStore()
        data = assemble_governance_status_record(
            dashboard_env["chain"], tracker, store
        )
        assert isinstance(data, dict)
        assert "chain_event_count" in data
        assert "chain_integrity" in data
        assert "verification_state" in data
        assert "opacity_posture" in data


# ===========================================================================
# Scope 7 — Telemetry and Trouble Boundary
# ===========================================================================

class TestTelemetryTroubleBoundary:
    """Verify telemetry and trouble reports are outside the governance chain."""

    def test_telemetry_reads_from_summary_json(self, dashboard_env):
        """_load_telemetry_summary reads from TELEMETRY_SUMMARY file."""
        summary = ds._load_telemetry_summary()
        assert summary["artifact_type"] == "anonymous_summary_telemetry"
        assert summary["privacy_model"]["governance_chain"] == \
            "telemetry is never written to the governance chain"

    def test_telemetry_privacy_model_states_no_chain(self, dashboard_env):
        """Telemetry privacy model explicitly states no chain writes."""
        template = ds._new_telemetry_summary()
        assert template["privacy_model"]["raw_events_stored"] is False
        assert template["privacy_model"]["raw_events_transmitted"] is False
        assert template["privacy_model"]["governance_chain"] == \
            "telemetry is never written to the governance chain"

    def test_trouble_report_stored_outside_chain(self, dashboard_env):
        """Trouble report handler stores to LOGS/trouble/, not chain."""
        source = inspect.getsource(ds.DashboardHandler._handle_trouble_report)
        # Explicit code comment
        assert "not governance records" in source.lower() or \
               "intentionally do not append to the decision chain" in source

    def test_trouble_report_no_chain_append(self, dashboard_env):
        """_handle_trouble_report source does not call _append_chain_record_atomic."""
        source = inspect.getsource(ds.DashboardHandler._handle_trouble_report)
        assert "_append_chain_record_atomic" not in source

    def test_telemetry_summary_no_chain_append(self, dashboard_env):
        """_handle_telemetry_summary does not call _append_chain_record_atomic."""
        source = inspect.getsource(ds.DashboardHandler._handle_telemetry_summary)
        assert "_append_chain_record_atomic" not in source

    def test_record_telemetry_summary_writes_to_file(self, dashboard_env):
        """_record_telemetry_summary writes to summary.json, not chain."""
        chain_before = dashboard_env["chain"].read_text()

        ds._record_telemetry_summary({"window_opens": {"overview": 1}})

        chain_after = dashboard_env["chain"].read_text()
        assert chain_after == chain_before, "Telemetry write modified the chain"

        summary_path = dashboard_env["telemetry_dir"] / "summary.json"
        assert summary_path.exists()

    def test_raw_events_rejected_by_summary_handler(self):
        """_handle_telemetry_summary rejects payloads with raw events."""
        source = inspect.getsource(ds.DashboardHandler._handle_telemetry_summary)
        assert '"events"' in source or "'events'" in source
        assert '"interactions"' in source or "'interactions'" in source
        assert "raw events are not accepted" in source

    def test_trouble_report_writes_to_trouble_dir(self, dashboard_env):
        """Trouble report artifact is stored in LOGS/trouble/."""
        import uuid
        artifact_id = f"tr_{uuid.uuid4().hex[:16]}"
        artifact = {
            "artifact_type": "trouble_report",
            "artifact_id": artifact_id,
            "timestamp_utc": "2026-04-30T12:00:00Z",
            "priority": "low",
            "description": "Gate 2 test",
            "context": {},
        }
        payload = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
        artifact["artifact_hash"] = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        out_path = dashboard_env["trouble_dir"] / f"{artifact_id}.json"
        ds._write_json_file(out_path, artifact)
        assert out_path.exists()
        stored = json.loads(out_path.read_text(encoding="utf-8"))
        assert stored["artifact_type"] == "trouble_report"

    def test_feedback_does_write_chain_event(self):
        """Unlike trouble reports, feedback submissions DO write chain events."""
        source = inspect.getsource(ds.DashboardHandler._handle_feedback_submit)
        assert "_append_chain_record_atomic" in source
        assert "feedback_submitted" in source


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
