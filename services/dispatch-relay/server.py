#!/usr/bin/env python3
"""Dispatch Relay MCP Server — minimal Streamable HTTP server for dispatch lifecycle.

Tools: submit_dispatch, list_dispatches, claim_dispatch, complete_dispatch
Transport: MCP Streamable HTTP (POST /mcp)
Auth: Bearer token
Storage: SQLite with WAL mode
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get(
    "DISPATCH_DB_PATH",
    str(Path(__file__).parent / "dispatch.db"),
)
BEARER_TOKEN = os.environ.get("DISPATCH_BEARER_TOKEN", "")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_db() -> sqlite3.Connection:
    """Return a per-thread SQLite connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def _init_db() -> None:
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dispatches (
            dispatch_id   TEXT PRIMARY KEY,
            created_utc   TEXT NOT NULL,
            target_agent  TEXT NOT NULL,
            classification TEXT NOT NULL,
            objective     TEXT NOT NULL,
            body_md       TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            claimed_by    TEXT,
            claimed_at    TEXT,
            result_status TEXT,
            result_summary TEXT,
            completed_at  TEXT
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp_server = FastMCP(
    "dispatch-relay",
    stateless_http=True,
)


@mcp_server.tool()
def submit_dispatch(
    dispatch_id: str,
    target_agent: str,
    classification: str,
    objective: str,
    body_md: str,
) -> str:
    """Create a new dispatch for a build agent to pick up.

    Args:
        dispatch_id: Unique dispatch identifier (e.g. "D-020")
        target_agent: Agent that should handle this dispatch (e.g. "cecil", "codex")
        classification: Dispatch type — BUILD, INVESTIGATE, or FIX
        objective: Short one-line summary of the task
        body_md: Full dispatch body in markdown
    """
    now = datetime.now(timezone.utc).isoformat()
    db = _get_db()
    try:
        db.execute(
            """INSERT INTO dispatches
               (dispatch_id, created_utc, target_agent, classification, objective, body_md, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (dispatch_id, now, target_agent, classification, objective, body_md),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return json.dumps({"error": f"Dispatch {dispatch_id} already exists"})
    return json.dumps({"ok": True, "dispatch_id": dispatch_id, "status": "pending", "created_utc": now})


@mcp_server.tool()
def list_dispatches(
    target_agent: str = "",
    status: str = "",
) -> str:
    """List dispatches, optionally filtered by target_agent and/or status.

    Args:
        target_agent: Filter by target agent (empty string = all agents)
        status: Filter by status: pending, claimed, or completed (empty string = all)
    """
    db = _get_db()
    clauses = []
    params: list = []
    if target_agent:
        clauses.append("target_agent = ?")
        params.append(target_agent)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        f"SELECT dispatch_id, target_agent, classification, objective, status, created_utc, claimed_by, result_status FROM dispatches{where} ORDER BY created_utc DESC",
        params,
    ).fetchall()
    return json.dumps([dict(r) for r in rows])


@mcp_server.tool()
def claim_dispatch(dispatch_id: str, claiming_agent: str) -> str:
    """Atomically claim a pending dispatch. Returns the full dispatch body.

    Args:
        dispatch_id: The dispatch to claim
        claiming_agent: Name of the agent claiming (e.g. "cecil")
    """
    now = datetime.now(timezone.utc).isoformat()
    db = _get_db()
    cur = db.execute(
        """UPDATE dispatches SET status='claimed', claimed_by=?, claimed_at=?
           WHERE dispatch_id=? AND status='pending'""",
        (claiming_agent, now, dispatch_id),
    )
    db.commit()
    if cur.rowcount == 0:
        row = db.execute("SELECT status FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
        if row is None:
            return json.dumps({"error": f"Dispatch {dispatch_id} not found"})
        return json.dumps({"error": f"Dispatch {dispatch_id} is already {row['status']}"})
    row = db.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
    return json.dumps(dict(row))


@mcp_server.tool()
def complete_dispatch(
    dispatch_id: str,
    result_status: str,
    result_summary: str,
) -> str:
    """Mark a claimed dispatch as completed.

    Args:
        dispatch_id: The dispatch to complete
        result_status: Outcome — success, partial, or failed
        result_summary: Brief text describing the result
    """
    now = datetime.now(timezone.utc).isoformat()
    db = _get_db()
    cur = db.execute(
        """UPDATE dispatches SET status='completed', result_status=?, result_summary=?, completed_at=?
           WHERE dispatch_id=? AND status='claimed'""",
        (result_status, result_summary, now, dispatch_id),
    )
    db.commit()
    if cur.rowcount == 0:
        row = db.execute("SELECT status FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
        if row is None:
            return json.dumps({"error": f"Dispatch {dispatch_id} not found"})
        return json.dumps({"error": f"Dispatch {dispatch_id} is {row['status']}, expected claimed"})
    return json.dumps({"ok": True, "dispatch_id": dispatch_id, "result_status": result_status, "completed_at": now})


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not BEARER_TOKEN:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth == f"Bearer {BEARER_TOKEN}":
            return await call_next(request)
        return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _init_db()

    # Get the underlying Starlette app from FastMCP
    app = mcp_server.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)

    import uvicorn
    port = int(os.environ.get("DISPATCH_PORT", "8765"))
    print(f"Dispatch Relay MCP server starting on port {port}")
    print(f"DB: {DB_PATH}")
    print(f"Auth: {'enabled' if BEARER_TOKEN else 'DISABLED (no DISPATCH_BEARER_TOKEN set)'}")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
