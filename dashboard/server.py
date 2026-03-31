#!/usr/bin/env python3
"""
Atested Governance Dashboard — lightweight HTTP server.

Serves the dashboard UI files and JSON API endpoints backed by the
governance chain readout functions.  Started by the governance_dashboard
MCP tool; not intended for direct invocation by operators.
"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
MCP_DIR = REPO / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from storage_contract import runtime_root

RUNTIME = runtime_root(REPO)
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"
RECORDS_DIR = RUNTIME / "LOGS" / "records"

# Lazy-loaded helpers
_verification_tracker = None
_approval_store = None


def _get_verification_tracker():
    global _verification_tracker
    if _verification_tracker is None:
        from verification import load_verification_state_from_chain
        _verification_tracker = (
            load_verification_state_from_chain(str(CHAIN))
            if CHAIN.exists()
            else __import__("verification").VerificationStateTracker()
        )
    return _verification_tracker


def _get_approval_store():
    global _approval_store
    if _approval_store is None:
        from approval_store import load_approval_store_from_chain, ApprovalStore
        _approval_store = (
            load_approval_store_from_chain(str(CHAIN))
            if CHAIN.exists()
            else ApprovalStore()
        )
    return _approval_store


def _json_response(handler, data, status=200):
    body = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


DASHBOARD_UI_DIR = REPO / "dashboard" / "ui"


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serves dashboard UI files and /api/* JSON endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_UI_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed)
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass  # Silence request logs

    def _handle_api(self, parsed):
        params = parse_qs(parsed.query)

        def qs(key, default=""):
            v = params.get(key, [default])
            return v[0] if v else default

        def qs_int(key, default=0):
            try:
                return int(qs(key, str(default)))
            except (ValueError, TypeError):
                return default

        path = parsed.path

        if path == "/api/status":
            from readout import assemble_governance_status_record
            window = qs_int("window") or None
            data = assemble_governance_status_record(
                CHAIN, _get_verification_tracker(), _get_approval_store(),
                window=window,
            )
            _json_response(self, data)

        elif path == "/api/activity":
            from readout import governance_activity_view
            data = governance_activity_view(
                CHAIN,
                limit=qs_int("limit", 50),
                offset=qs_int("offset", 0),
                governed_family=qs("governed_family") or None,
                event_category=qs("event_category") or None,
                resolution=qs("resolution") or None,
            )
            _json_response(self, data)

        elif path == "/api/approvals":
            from readout import governance_approvals_view
            data = governance_approvals_view(CHAIN, _get_approval_store())
            _json_response(self, data)

        elif path == "/api/verification":
            from readout import governance_verification_view
            data = governance_verification_view(
                CHAIN, _get_verification_tracker(),
                governed_family=qs("governed_family") or None,
            )
            _json_response(self, data)

        elif path == "/api/audit/query":
            from readout import audit_query
            data = audit_query(
                CHAIN, RECORDS_DIR,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
                user_identity=qs("user_identity") or None,
                tool_name=qs("tool_name") or None,
                policy_decision=qs("policy_decision") or None,
                event_category=qs("event_category") or None,
                limit=qs_int("limit", 100),
                offset=qs_int("offset", 0),
            )
            _json_response(self, data)

        elif path == "/api/audit/record":
            from readout import audit_record_detail
            rid = qs("record_id")
            if not rid:
                _json_response(self, {"error": "record_id required"}, 400)
                return
            data = audit_record_detail(CHAIN, RECORDS_DIR, record_id=rid)
            _json_response(self, data)

        elif path == "/api/audit/report":
            from readout import audit_report
            data = audit_report(
                CHAIN, RECORDS_DIR,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
                group_by=qs("group_by", "tool"),
            )
            _json_response(self, data)

        elif path == "/api/users":
            from readout import load_chain_rows
            from collections import Counter
            users = Counter()
            rows = load_chain_rows(CHAIN)
            for rec in rows:
                uid = rec.get("user_identity")
                if uid:
                    users[uid] += 1
            if RECORDS_DIR.exists():
                for rfile in RECORDS_DIR.glob("*.record.json"):
                    try:
                        rec = json.loads(rfile.read_text(encoding="utf-8"))
                        uid = rec.get("user_identity")
                        if uid:
                            users[uid] += 1
                    except (json.JSONDecodeError, OSError):
                        continue
            _json_response(self, {
                "unique_users": len(users),
                "users": [{"identity": k, "count": v} for k, v in users.most_common()],
            })

        else:
            _json_response(self, {"error": "unknown endpoint"}, 404)


def main():
    port = int(os.environ.get("DASHBOARD_PORT", "9700"))
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
