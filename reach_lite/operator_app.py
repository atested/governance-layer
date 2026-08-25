"""WP-RL-008: directly runnable Reach Lite operator application.

Integrates the completed current-scope behavior (chat brief to agent
proposal, agent lifecycle, draft approval, run results, operator
settings) into one operator application that exposes Chat, Agents,
Approvals, Results, and Settings through one browser entry point.

Framework decisions (see docs/design/reach-lite-operator-application.md):
- Framework: Python standard library http.server (ThreadingHTTPServer).
  Zero new runtime dependencies; the same interpreter that runs
  "make test" starts the app.
- Source layout: single module, run with
  "python3 -m reach_lite.operator_app --port <port>".
- Port: 9700 by default (matching run-operator-ui.sh), overridable via
  --port or OPERATOR_UI_PORT.
- Transport: HTTP/1.1 JSON API plus server-rendered HTML views for the
  five destinations, all under one entry point ("/").
- Process supervision: one supervised foreground process; readiness is
  advertised via GET /api/health; no external supervisor required.

State is seeded from the domain layer (new_agent, transition_agent,
compose_drafts, apply_approval_action, interpret_brief) so the browser
operates on exactly the records the validator suite validates.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .domain import (
    AGENT_STATES,
    APPROVAL_ACTIONS,
    PROVIDERS,
    PROHIBITED_OPERATOR_CONTROLS,
    Agent,
    Connection,
    Opportunity,
    Person,
    Run,
    apply_approval_action,
    compose_drafts,
    draft_review_context,
    default_budget,
    default_schedule,
    interpret_brief,
    new_agent,
    transition_agent,
)

APP_NAME = "reach-lite-operator"
DEFAULT_PORT = 9700
DEFAULT_BIND = "127.0.0.1"
FIVE_DESTINATIONS = ("chat", "agents", "approvals", "results", "settings")
ACTIVATION_OPERATION_TEMPLATE = "python3 -m reach_lite.operator_app --port {port}"

_DESTINATION_TITLES = {
    "chat": "Chat",
    "agents": "Agents",
    "approvals": "Approvals",
    "results": "Results",
    "settings": "Settings",
}


class AppState:
    """In-memory operator state, guarded by a single lock."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.agents: list[Agent] = []
        self.runs: list[Run] = []
        self.opportunities: list[Opportunity] = []
        self.drafts: list[Any] = []
        self.connections: list[Connection] = []
        self.person: Person | None = None
        self.chat: dict[str, Any] = {"brief_text": None, "interpretation": None, "clarifications": []}


def seed_state() -> AppState:
    """Seed one live agent, one succeeded run, and three pending drafts."""
    state = AppState()
    agent = new_agent(
        "agent-llama",
        "Check r/LocalLLaMA on weekdays at 9am.",
        [{"kind": "subreddit", "value": "r/LocalLLaMA"}],
        {"include": "local model releases", "exclude": "vendor promotion"},
        mode="ask",
    )
    live = transition_agent(agent, "live")
    if live is not None:
        state.agents.append(live)

    state.runs.append(
        Run(
            run_id="run-001",
            agent_id="agent-llama",
            started_at="2026-08-23T09:00:00Z",
            finished_at="2026-08-23T09:06:00Z",
            sources_polled=["r/LocalLLaMA"],
            candidates_seen=12,
            candidates_qualified=3,
            drafts_produced=3,
            provider_used="local",
            token_cost=None,
            status="succeeded",
        )
    )

    opportunities = []
    for i in (1, 2, 3):
        opportunities.append(
            Opportunity(
                opportunity_id=f"opp-00{i}",
                run_id="run-001",
                channel="reddit",
                source_url=f"https://reddit.com/r/LocalLLaMA/comments/{i}",
                author_handle="@modelposter",
                excerpt=f"Local model release discussion {i}.",
                qualify_score=0.85,
                qualify_reason="matches qualification intent",
                person_id=None,
            )
        )
    state.opportunities.extend(opportunities)
    state.drafts.extend(compose_drafts(opportunities, provider_used="local"))

    state.connections.append(
        Connection(
            connection_id="conn-001",
            channel="reddit",
            auth_kind="oauth",
            scopes=["read", "write"],
            status="connected",
            expires_at=None,
        )
    )
    state.person = Person(
        person_id="person-001",
        handles=[{"channel": "reddit", "handle": "@modelposter"}],
        first_seen="2026-08-01T00:00:00Z",
        interactions=[],
        notes="Single-operator boundary.",
    )
    return state


def _nav_html() -> str:
    links = "".join(
        f'<a href="/{dest}" data-destination="{dest}">{_DESTINATION_TITLES[dest]}</a>'
        for dest in FIVE_DESTINATIONS
    )
    return f'<nav class="operator-nav"><a href="/" data-destination="home">{APP_NAME}</a>{links}</nav>'


def _dashboard_html() -> str:
    panels = "".join(
        f'<section class="panel panel-{dest}" id="panel-{dest}"><h2>{_DESTINATION_TITLES[dest]}</h2><div class="body" id="body-{dest}">loading /api/{dest}</div></section>'
        for dest in FIVE_DESTINATIONS
    )
    script = (
        "const dests=["
        + ",".join(f'"{d}"' for d in FIVE_DESTINATIONS)
        + "];"
        "for(const d of dests){fetch('/api/'+d).then(r=>r.json())"
        ".then(j=>{document.getElementById('body-'+d).textContent=JSON.stringify(j,null,2);});}"
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{APP_NAME}</title></head>"
        f'<body class="dashboard"><main>{_nav_html()}{panels}</main>'
        f"<script>{script}</script></body></html>"
    )


def _destination_html(dest: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{_DESTINATION_TITLES[dest]} - {APP_NAME}</title></head>"
        f'<body class="view view-{dest}"><main>{_nav_html()}'
        f"<h1>{_DESTINATION_TITLES[dest]}</h1>"
        f'<div class="body" id="body-{dest}">loading /api/{dest}</div>'
        f"</main></body></html>"
    )


def _agent_payload(agent: Agent) -> dict[str, Any]:
    return dataclasses.asdict(agent)


def _draft_payload(draft: Any) -> dict[str, Any]:
    return dataclasses.asdict(draft)


def make_handler(state: AppState):
    class OperatorHandler(BaseHTTPRequestHandler):
        server_version = APP_NAME
        sys_version = ""

        def log_message(self, *args: Any) -> None:
            pass

        # -- plumbing -----------------------------------------------------
        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, body: str, status: int = 200) -> None:
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                value = json.loads(raw.decode("utf-8"))
                return value if isinstance(value, dict) else None
            except (ValueError, UnicodeDecodeError):
                return None

        # -- GET routes ---------------------------------------------------
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send_html(_dashboard_html())
                return
            if path in ("/chat", "/agents", "/approvals", "/results", "/settings"):
                self._send_html(_destination_html(path[1:]))
                return
            if path == "/api/health":
                self._send_json(
                    {
                        "status": "ok",
                        "app": APP_NAME,
                        "entry_point": "/",
                        "destinations": list(FIVE_DESTINATIONS),
                    }
                )
                return
            with state.lock:
                if path == "/api/chat":
                    self._send_json(
                        {
                            "brief_text": state.chat.get("brief_text"),
                            "interpretation": state.chat.get("interpretation"),
                            "clarifications": state.chat.get("clarifications", []),
                            "proposal": {
                                "editable": True,
                                "readable": True,
                                "choices": ["create_agent", "not_now"],
                            },
                        }
                    )
                    return
                if path == "/api/agents":
                    self._send_json({"agents": [_agent_payload(a) for a in state.agents]})
                    return
                if path == "/api/approvals":
                    by_opportunity = {o.opportunity_id: o for o in state.opportunities}
                    drafts = []
                    for draft in state.drafts:
                        if draft.state != "pending":
                            continue
                        opportunity = by_opportunity.get(draft.opportunity_id)
                        context = draft_review_context(draft, opportunity) if opportunity else None
                        drafts.append(
                            {"draft": _draft_payload(draft), "review_context": context}
                        )
                    self._send_json({"drafts": drafts})
                    return
                if path == "/api/results":
                    by_opportunity = {o.opportunity_id: o for o in state.opportunities}
                    runs = []
                    for run in state.runs:
                        run_drafts = [
                            d
                            for d in state.drafts
                            if by_opportunity.get(d.opportunity_id)
                            and by_opportunity[d.opportunity_id].run_id == run.run_id
                        ]
                        by_state: dict[str, int] = {}
                        for d in run_drafts:
                            by_state[d.state] = by_state.get(d.state, 0) + 1
                        runs.append(
                            {
                                "run": dataclasses.asdict(run),
                                "summary": {
                                    "candidates_seen": run.candidates_seen,
                                    "candidates_qualified": run.candidates_qualified,
                                    "drafts_produced": run.drafts_produced,
                                    "drafts_by_state": by_state,
                                },
                            }
                        )
                    self._send_json({"runs": runs})
                    return
                if path == "/api/settings":
                    self._send_json(
                        {
                            "entry_point": "/",
                            "current_scope": [
                                {
                                    "control": "schedule_defaults",
                                    "value": default_schedule(),
                                    "enabled": True,
                                },
                                {
                                    "control": "budget_defaults",
                                    "value": default_budget(),
                                    "enabled": True,
                                },
                                {
                                    "control": "provider_routing",
                                    "value": list(PROVIDERS),
                                    "enabled": True,
                                },
                                {
                                    "control": "approval_workflow",
                                    "value": list(APPROVAL_ACTIONS),
                                    "enabled": True,
                                },
                            ],
                            "deferred": [
                                {"control": "post_draft", "enabled": False},
                                {"control": "person_memory", "enabled": False},
                            ],
                        }
                    )
                    return
            self._send_json({"error": "not found"}, 404)

        # -- POST routes --------------------------------------------------
        def do_POST(self) -> None:
            path = urlparse(self.path).path
            body = self._read_json()
            if body is None:
                self._send_json({"error": "invalid json body"}, 400)
                return
            parts = [p for p in path.split("/") if p]

            if path == "/api/chat" and "brief_text" in body:
                values, clarifications = interpret_brief(body["brief_text"])
                with state.lock:
                    state.chat = {
                        "brief_text": body["brief_text"],
                        "interpretation": values,
                        "clarifications": clarifications,
                    }
                self._send_json(
                    {
                        "brief_text": body["brief_text"],
                        "interpretation": values,
                        "clarifications": clarifications,
                        "proposal": {
                            "editable": True,
                            "readable": True,
                            "choices": ["create_agent", "not_now"],
                        },
                    }
                )
                return

            if path == "/api/agents":
                agent = new_agent(
                    body.get("agent_id", f"agent-{len(state.agents) + 1:03d}"),
                    body.get("brief_text", ""),
                    body.get("sources", []),
                    body.get("qualifier", {}),
                    mode=body.get("mode", "ask"),
                )
                with state.lock:
                    state.agents.append(agent)
                self._send_json({"created": True, "agent": _agent_payload(agent)})
                return

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "agents" and parts[3] == "transition":
                agent_id = parts[2]
                new_state = body.get("state")
                if new_state not in AGENT_STATES:
                    self._send_json({"error": "unknown agent state"}, 409)
                    return
                with state.lock:
                    target = next((a for a in state.agents if a.agent_id == agent_id), None)
                    if target is None:
                        self._send_json({"error": "agent not found"}, 404)
                        return
                    updated = transition_agent(target, new_state)
                    if updated is None:
                        self._send_json({"error": "invalid transition"}, 409)
                        return
                    state.agents.remove(target)
                    state.agents.append(updated)
                self._send_json({"agent": _agent_payload(updated)})
                return

            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "approvals"
                and parts[3] == "action"
            ):
                draft_id = parts[2]
                action = body.get("action")
                if action not in APPROVAL_ACTIONS:
                    self._send_json({"error": "unknown approval action"}, 400)
                    return
                with state.lock:
                    target = next((d for d in state.drafts if d.draft_id == draft_id), None)
                    if target is None:
                        self._send_json({"error": "draft not found"}, 404)
                        return
                    updated = apply_approval_action(
                        target,
                        action,
                        new_body=body.get("new_body"),
                        new_draft_id=body.get("new_draft_id"),
                    )
                    if updated is None:
                        self._send_json({"error": "invalid approval action"}, 400)
                        return
                    state.drafts.remove(target)
                    state.drafts.append(updated)
                self._send_json({"draft": _draft_payload(updated)})
                return

            self._send_json({"error": "not found"}, 404)

    return OperatorHandler


def create_app(port: int = 0, bind: str = DEFAULT_BIND, state: AppState | None = None) -> tuple[ThreadingHTTPServer, AppState]:
    """Build the operator application server; returns (server, state)."""
    app_state = state if state is not None else seed_state()
    server = ThreadingHTTPServer((bind, port), make_handler(app_state))
    return server, app_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reach_lite.operator_app")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("OPERATOR_UI_PORT", DEFAULT_PORT)),
        help="TCP port to bind (default: 9700)",
    )
    parser.add_argument("--bind", default=DEFAULT_BIND, help="Interface to bind (default: 127.0.0.1)")
    args = parser.parse_args(argv)
    server, _state = create_app(port=args.port, bind=args.bind)
    host, actual_port = server.server_address[:2]
    print(
        f"{APP_NAME} listening on http://{host}:{actual_port} "
        f"(entry point /; destinations: {', '.join(FIVE_DESTINATIONS)})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
