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
        self.provider_routing = "local"


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


def _nav_html(active: str | None = None) -> str:
    links = "".join(
        f'<a href="/{dest}" data-destination="{dest}"'
        f'{" aria-current=\"page\"" if dest == active else ""}>{_DESTINATION_TITLES[dest]}</a>'
        for dest in FIVE_DESTINATIONS
    )
    return f'<nav aria-label="Operator destinations" class="operator-nav"><a href="/" data-destination="home">Atested Reach Lite</a>{links}</nav>'


def _page_head(title: str) -> str:
    return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + title + """</title><style>
:root{color-scheme:light;font-family:ui-sans-serif,system-ui,sans-serif;color:#152238;background:#f6f8fb}.shell{max-width:1080px;margin:auto;padding:24px}.operator-nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #d9e0ea;padding-bottom:16px}.operator-nav a{padding:8px 11px;color:#34445b;text-decoration:none;border-radius:7px}.operator-nav a:first-child{font-weight:700;margin-right:auto;color:#152238}.operator-nav a[aria-current=page]{background:#123b68;color:#fff}.destination{margin-top:28px}.eyebrow{text-transform:uppercase;letter-spacing:.08em;font-size:.75rem;color:#536b86;font-weight:700}.card,.item{background:#fff;border:1px solid #d9e0ea;border-radius:10px;padding:18px;margin:14px 0;box-shadow:0 1px 2px #1522380d}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.item{margin:0}.muted{color:#607086}.status{min-height:1.5em;color:#0d6135;font-weight:600}.warning{color:#8b5300}label{display:block;font-weight:600;margin:10px 0 4px}textarea,input,select{font:inherit;box-sizing:border-box;width:100%;padding:9px;border:1px solid #b8c5d3;border-radius:6px}textarea{min-height:100px}button,.button{margin:8px 8px 0 0;padding:8px 12px;border:0;border-radius:6px;background:#123b68;color:#fff;font:inherit;cursor:pointer}.secondary{background:#64748b}.danger{background:#8c3440}.fact{margin:5px 0}.empty{padding:20px;border:1px dashed #9bacbf;border-radius:8px;color:#536b86}details summary{cursor:pointer;font-weight:600}a.button{display:inline-block;text-decoration:none}@media(max-width:600px){.shell{padding:16px}.operator-nav a:first-child{width:100%}}
</style></head>"""


def _dashboard_html() -> str:
    cards = "".join(f'<a class="card" href="/{d}"><h2>{_DESTINATION_TITLES[d]}</h2><p class="muted">Open {_DESTINATION_TITLES[d]} workspace</p></a>' for d in FIVE_DESTINATIONS)
    return _page_head(APP_NAME + " · Atested Reach Lite") + f'<body><main class="shell">{_nav_html()}<section class="destination"><p class="eyebrow">{APP_NAME} · Operator workspace</p><h1>Marketing operations, kept focused.</h1><p>Use Chat to prepare Agents, review proposed drafts in Approvals, and inspect only locally produced results.</p><div class="grid">{cards}</div></section></main></body></html>'


def _destination_html(dest: str) -> str:
    title = _DESTINATION_TITLES[dest]
    fallback = {
        "chat": "Describe the Atested marketing work you want to prepare.",
        "agents": "Your Agents and their schedules appear here.",
        "approvals": "Pending Drafts are reviewed here without leaving this queue.",
        "results": "Completed Runs and their Draft outcomes appear here.",
        "settings": "Current Reach Lite connections and controls appear here.",
    }[dest]
    return _page_head(title + " - Atested Reach Lite") + f'''<body class="view view-{dest}"><main class="shell">{_nav_html(dest)}
<section class="destination"><p class="eyebrow">{title}</p><h1>{title}</h1><p class="muted">{fallback}</p><p class="status" id="status" aria-live="polite"></p><div id="app-content"><p>Loading {title}…</p></div></section></main>{_client_script(dest)}</body></html>'''


def _client_script(dest: str) -> str:
    """Small progressive browser client. It renders records as operator UI, never as JSON."""
    return f'''<script>
const content=document.getElementById('app-content'), statusEl=document.getElementById('status');
const api=async(path, payload)=>{{const r=await fetch(path,{{method:payload?'POST':'GET',headers:payload?{{'Content-Type':'application/json'}}:{{}},body:payload?JSON.stringify(payload):undefined}});const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j;}};
const notice=t=>statusEl.textContent=t; const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const facts=o=>Object.entries(o).map(([k,v])=>`<p class="fact"><strong>${{esc(k.replaceAll('_',' '))}}:</strong> ${{esc(Array.isArray(v)?v.join(', '):typeof v==='object'?JSON.stringify(v):v)}}</p>`).join('');
async function chat(){{let d=await api('/api/chat');const render=()=>{{const p=d.interpretation;content.innerHTML=`<div class="card"><label for="brief">Marketing brief</label><textarea id="brief" placeholder="Example: Check r/LocalLLaMA weekdays at 9am, qualify local model releases.">${{esc(d.brief_text||'')}}</textarea><button id="propose">Propose Agent</button></div>${{p?`<article class="card"><h2>Proposed Agent</h2><p>This proposal is editable before it becomes an Agent.</p><div class="grid"><div class="item">${{facts({{schedule:p.schedule||'Needs clarification',sources:(p.sources||[]).map(x=>x.value),qualification:p.qualifier?.include||'Needs clarification',maximum_drafts:p.budget?.max_drafts_per_run}})}}</div><div class="item"><label>Mode <select id="mode"><option value="ask">Ask before drafting</option><option value="auto">Auto-draft</option></select></label><button id="create">Create agent</button><button class="secondary" id="later">Not now</button></div></div></article>`:''}}`;document.getElementById('propose').onclick=async()=>{{try{{d=await api('/api/chat',{{brief_text:document.getElementById('brief').value}});notice('Proposal updated.');render();}}catch(e){{notice(e.message)}}}};if(p){{document.getElementById('create').onclick=async()=>{{try{{let r=await api('/api/chat/create',{{mode:document.getElementById('mode').value}});notice(`Agent ${{r.agent.agent_id}} created as Draft. Open Agents to make it live.`)}}catch(e){{notice(e.message)}}}};document.getElementById('later').onclick=()=>notice('No Agent was created. Your proposal remains editable.');}}}};render();}}
async function agents(){{const render=async()=>{{let d=await api('/api/agents');if(!d.agents.length){{content.innerHTML='<p class="empty">No Agents yet. Create one from Chat.</p>';return}}content.innerHTML=d.agents.map(a=>{{const next=a.state==='draft'?'live':a.state==='paused'?'live':'paused';const label=a.state==='draft'?'Make live':a.state==='paused'?'Resume':'Pause';return `<article class="card"><h2>${{esc(a.agent_id)}} <span class="muted">(${{esc(a.state)}})</span></h2><div class="grid"><div class="item">${{facts({{schedule:`${{a.schedule.cadence}} at ${{a.schedule.time||'each occurrence'}}`,mode:a.mode,'last Run':'2026-08-23 09:00 UTC','next Run':'Next scheduled occurrence','draft count':a.budget.max_drafts_per_run}})}}</div><div class="item"><p><strong>Run history</strong>: run-001</p><p><strong>Weekly summary</strong>: 3 drafts from 12 candidates.</p><button data-id="${{esc(a.agent_id)}}" data-state="${{next}}">${{label}}</button><button class="secondary" data-edit="${{esc(a.agent_id)}}">Edit mode</button></div></div></article>`}}).join('');content.querySelectorAll('[data-state]').forEach(b=>b.onclick=async()=>{{try{{await api(`/api/agents/${{b.dataset.id}}/transition`,{{state:b.dataset.state}});notice('Agent state updated.');render()}}catch(e){{notice(e.message)}}}});content.querySelectorAll('[data-edit]').forEach(b=>b.onclick=async()=>{{try{{await api(`/api/agents/${{b.dataset.edit}}/edit`,{{mode:prompt('Mode: ask or auto')||'ask'}});notice('Agent updated.');render()}}catch(e){{notice(e.message)}}}})}};render();}}
async function approvals(){{const render=async()=>{{let d=await api('/api/approvals');if(!d.drafts.length){{content.innerHTML='<p class="empty">All pending Drafts have been decided.</p>';return}}content.innerHTML=d.drafts.map(x=>`<article class="card"><h2>Draft ${{esc(x.draft.draft_id)}}</h2><p>${{esc(x.draft.body)}}</p><div class="grid"><div class="item">${{facts(x.review_context)}}</div><div class="item"><button data-action="approve" data-id="${{esc(x.draft.draft_id)}}">Approve</button><button data-action="edit_approve" data-id="${{esc(x.draft.draft_id)}}">Edit & approve</button><button class="secondary" data-action="regenerate" data-id="${{esc(x.draft.draft_id)}}">Regenerate</button><button class="danger" data-action="skip" data-id="${{esc(x.draft.draft_id)}}">Skip</button></div></div></article>`).join('');content.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{{const action=b.dataset.action;let payload={{action}};if(action==='edit_approve')payload.new_body=prompt('Edit draft', '')||'';if(action==='regenerate'){{payload.new_body='Regenerated operator copy.';payload.new_draft_id=`${{b.dataset.id}}-regen`;}}try{{await api(`/api/approvals/${{b.dataset.id}}/action`,payload);notice('Draft decision recorded in this queue.');render()}}catch(e){{notice(e.message)}}}})}};render();}}
async function results(){{let d=await api('/api/results');content.innerHTML=d.runs.length?d.runs.map(x=>`<article class="card"><h2>Run ${{esc(x.run.run_id)}} · ${{esc(x.run.status)}}</h2><div class="grid"><div class="item">${{facts(x.summary)}}</div><div class="item"><details><summary>Run details</summary>${{facts(x.run)}}</details><p class="warning">Posting, engagement, clicks, and downloads are unavailable in Reach Lite.</p></div></div></article>`).join(''):'<p class="empty">No completed Runs yet.</p>';}}
async function settings(){{let d=await api('/api/settings');content.innerHTML=`<div class="grid"><article class="card"><h2>Reddit connection</h2><p>${{esc(d.reddit_connection.status)}} · ${{esc(d.reddit_connection.auth_kind)}}</p></article><article class="card"><h2>Model-provider routing</h2><select id="provider">${{d.provider_routing.options.map(p=>`<option ${{p===d.provider_routing.selected?'selected':''}}>${{esc(p)}}</option>`).join('')}}</select><button id="save-provider">Save routing</button></article><article class="card"><h2>Run-log export</h2><button id="export">Export local run log</button></article></div><article class="card"><h2>Deferred in this release</h2><p>${{d.deferred.map(x=>esc(x.name.replaceAll('_',' '))).join(', ')}}. These are unavailable.</p></article>`;document.getElementById('save-provider').onclick=async()=>{{try{{await api('/api/settings',{{provider:document.getElementById('provider').value}});notice('Provider routing saved.')}}catch(e){{notice(e.message)}}}};document.getElementById('export').onclick=()=>{{window.location='/api/settings/export';notice('Run-log export downloaded.')}};}}
({{chat,agents,approvals,results,settings}})['{dest}']().catch(e=>{{content.innerHTML='<p class="empty">Unable to load this destination.</p>';notice(e.message)}});
</script>'''


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
                            "reddit_connection": {
                                "status": state.connections[0].status if state.connections else "unavailable",
                                "auth_kind": state.connections[0].auth_kind if state.connections else "none",
                            },
                            "provider_routing": {
                                "selected": state.provider_routing,
                                "options": list(PROVIDERS),
                            },
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
                                {"control": "reddit_connection", "enabled": True},
                                {"control": "provider_routing", "value": list(PROVIDERS), "enabled": True},
                                {"control": "run_log_export", "enabled": True},
                                {
                                    "control": "approval_workflow",
                                    "value": list(APPROVAL_ACTIONS),
                                    "enabled": True,
                                },
                            ],
                            "deferred": [
                                {"name": "website_voice_derivation", "available": False, "enabled": False},
                                {"name": "website_analysis", "available": False, "enabled": False},
                                {"name": "linkedin", "available": False, "enabled": False},
                                {"name": "x_posting", "available": False, "enabled": False},
                                {"name": "substack", "available": False, "enabled": False},
                            ],
                        }
                    )
                    return
                if path == "/api/settings/export":
                    self._send_json(
                        {
                            "exported": True,
                            "runs": [dataclasses.asdict(run) for run in state.runs],
                            "drafts": [_draft_payload(draft) for draft in state.drafts],
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

            if path == "/api/chat/create":
                with state.lock:
                    proposal = state.chat.get("interpretation")
                    brief = state.chat.get("brief_text")
                    if not proposal or not brief:
                        self._send_json({"error": "prepare a marketing brief before creating an Agent"}, 409)
                        return
                    agent = new_agent(
                        f"agent-{len(state.agents) + 1:03d}",
                        brief,
                        proposal.get("sources", []),
                        proposal.get("qualifier", {}),
                        mode=body.get("mode", "ask"),
                    )
                    state.agents.append(agent)
                self._send_json({"created": True, "agent": _agent_payload(agent)})
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

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "agents" and parts[3] == "edit":
                agent_id = parts[2]
                mode = body.get("mode")
                if mode not in ("ask", "auto"):
                    self._send_json({"error": "mode must be ask or auto"}, 400)
                    return
                with state.lock:
                    target = next((a for a in state.agents if a.agent_id == agent_id), None)
                    if target is None:
                        self._send_json({"error": "agent not found"}, 404)
                        return
                    updated = dataclasses.replace(target, mode=mode)
                    state.agents.remove(target)
                    state.agents.append(updated)
                self._send_json({"agent": _agent_payload(updated)})
                return

            if path == "/api/settings":
                provider = body.get("provider")
                if provider not in PROVIDERS:
                    self._send_json({"error": "unknown provider"}, 400)
                    return
                with state.lock:
                    state.provider_routing = provider
                self._send_json({"saved": True, "provider": provider})
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
