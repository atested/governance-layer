"""WP-RL-007 end-to-end acceptance and evidence reconciliation.

Assembles conforming fixtures for every source validator, runs the complete
validator catalog (all 43 source validators plus
ValidatorCatalogCompletenessValidator), and reports a single reconciliation
verdict. The reconciliation makes no posting, attestation, multi-operator, or
deferred-result claim: those boundaries are enforced by the source validators
themselves (NoOutboundActionValidator, AttestationDropValidator,
SingleOperatorBoundaryValidator, and WalkingSkeletonResultsValidator).
"""

from __future__ import annotations

from typing import Any

from .domain import (
    Agent,
    Connection,
    Draft,
    Opportunity,
    Person,
    ProviderTaskInvocation,
    Run,
    ScheduleTrigger,
    append_record,
    apply_approval_action,
    compose_drafts,
    default_budget,
    default_schedule,
    interpret_brief,
    new_agent,
    retrieve_authorized_candidates,
)
from .validators import (
    COMPLETE_VALIDATOR_CATALOG,
    PROVIDERS,
    VALIDATOR_CATALOG,
    run_complete_catalog,
)


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_agent(agent_id="a1", state="live", **kw) -> Agent:
    agent = new_agent(
        agent_id,
        "Reach out to r/SaaS on weekdays at 09:00.",
        [{"kind": "subreddit", "value": "r/SaaS"}],
        {"include": "feedback", "exclude": "promotion"},
    )
    agent.state = state
    for key, value in kw.items():
        setattr(agent, key, value)
    return agent


def make_run(run_id="r1", agent_id="a1", **kw) -> Run:
    base = dict(
        run_id=run_id,
        agent_id=agent_id,
        started_at="2026-08-21T09:00:00",
        finished_at="2026-08-21T09:05:00",
        sources_polled=["r/SaaS"],
        candidates_seen=10,
        candidates_qualified=4,
        drafts_produced=2,
        provider_used="deepclaude",
        token_cost=1234,
        status="succeeded",
    )
    base.update(kw)
    return Run(**base)


def make_opportunity(opportunity_id="o1", run_id="r1", **kw) -> Opportunity:
    base = dict(
        opportunity_id=opportunity_id,
        run_id=run_id,
        channel="reddit",
        source_url="https://www.reddit.com/r/SaaS/comments/abc123",
        author_handle="u_alice",
        excerpt="We just launched and need feedback.",
        qualify_score=0.8,
        qualify_reason="matches brief qualification intent",
        person_id=None,
    )
    base.update(kw)
    return Opportunity(**base)


def make_draft(draft_id="d1", opportunity_id="o1", **kw) -> Draft:
    base = dict(
        draft_id=draft_id,
        opportunity_id=opportunity_id,
        body="Thanks for the specifics on your pricing.",
        channel="reddit",
        target_url="https://www.reddit.com/r/SaaS/comments/abc123",
        provider_used="deepclaude",
        attribution_link=None,
        state="pending",
    )
    base.update(kw)
    return Draft(**base)


def make_connection(connection_id="c1", **kw) -> Connection:
    base = dict(
        connection_id=connection_id,
        channel="reddit",
        auth_kind="script_credential",
        scopes=["read"],
        status="connected",
        expires_at=None,
    )
    base.update(kw)
    return Connection(**base)


def make_person(person_id="p1", **kw) -> Person:
    base = dict(
        person_id=person_id,
        handles=[{"value": "u_alice"}],
        first_seen="2026-08-01T00:00:00",
        interactions=[{"source": "opportunity", "ref": "o1"}],
        notes="",
    )
    base.update(kw)
    return Person(**base)


def make_invocation(invocation_id="i1", **kw) -> ProviderTaskInvocation:
    base = dict(
        invocation_id=invocation_id,
        task_type="chat",
        provider_requested="codex",
        provider_used="codex",
        input_ref="in1",
        result_ref="res1",
        started_at="2026-08-21T09:00:00",
        finished_at="2026-08-21T09:00:05",
        status="succeeded",
        failure_reason=None,
    )
    base.update(kw)
    return ProviderTaskInvocation(**base)


WORKED_BRIEF = (
    "Reach out to r/SaaS and r/startups on weekdays at 09:00. "
    "Qualify posts from founders asking for feedback. "
    "Exclude anything about hiring. "
    "Draft a reply, maximum of three drafts."
)

WORKED_EXPECTED = {
    "schedule": {"cadence": "weekly", "days": ["mon", "tue", "wed", "thu", "fri"], "time": "09:00"},
    "sources": [
        {"kind": "subreddit", "value": "r/SaaS"},
        {"kind": "subreddit", "value": "r/startups"},
    ],
    "qualifier": {
        "include": "posts from founders asking for feedback",
        "exclude": "anything about hiring",
    },
    "action": "draft_reply",
    "budget": {"max_surfaced_per_run": 5, "max_drafts_per_run": 3},
}


# ---------------------------------------------------------------------------
# Conforming fixtures for all 43 source validators.
# ---------------------------------------------------------------------------

def build_conforming_fixtures() -> dict[str, Any]:
    live = make_agent("a1", "live")
    run = make_run("r1", "a1")
    opp = make_opportunity("o1", "r1")
    draft = make_draft("d1", "o1")
    person = make_person("p1")

    chain = append_record(
        [], record_id="rec1", record_type="run", recorded_at="2026-08-21T09:00:00",
        subject_id="r1", payload={"status": "succeeded"},
    )
    chain = append_record(
        chain, record_id="rec2", record_type="opportunity",
        recorded_at="2026-08-21T09:01:00", subject_id="o1", payload={"score": 0.8},
    )

    qualifying_opp = make_opportunity("o2", "r1", source_url="https://www.reddit.com/r/SaaS/comments/def456", excerpt="We need feedback from founders.")
    clean_draft = make_draft("d2", "o2", body="Thanks for sharing your launch details.")

    candidate_auth = {
        "candidate_id": "cand1", "source": {"kind": "subreddit", "value": "r/SaaS"},
        "url": "https://www.reddit.com/r/SaaS/comments/abc123", "excerpt": "We need feedback.",
    }
    candidate_unauth = {
        "candidate_id": "cand2", "source": {"kind": "subreddit", "value": "r/Other"},
        "url": "https://www.reddit.com/r/Other/comments/xyz999", "excerpt": "promotion post.",
    }

    opp_known = make_opportunity("o3", "r1", author_handle="u_alice", person_id="p1",
        source_url="https://www.reddit.com/r/SaaS/comments/known1")
    opp_unknown = make_opportunity("o4", "r1", author_handle="u_bob", person_id=None,
        source_url="https://www.reddit.com/r/SaaS/comments/unknown1")

    return {
        # WP-RL-001
        "AgentAtomValidator": {
            "routes": ["chat", "agents", "approvals", "results", "settings"],
            "pipeline_controls": [],
            "agents": [live],
        },
        "BriefOnlyAuthoringValidator": {
            "persisted_agent": make_agent("a2", "live"),
            "prohibited_authoring": [],
        },
        "BriefInterpretationValidator": {
            "scenarios": [{
                "brief": WORKED_BRIEF,
                "interpreted": interpret_brief(WORKED_BRIEF)[0],
                "clarifications": interpret_brief(WORKED_BRIEF)[1],
                "expected": WORKED_EXPECTED,
                "required_missing": [],
            }]
        },
        "AgentLifecycleValidator": {
            "agents": [make_agent("a1", "live"), make_agent("a3", "draft"), make_agent("a4", "paused")],
            "transitions": [{"agent_id": "a1", "from": "draft", "to": "live"}],
            "runs": [run],
        },
        "RunAccountingValidator": {
            "runs": [
                {"run": run, "cost_available": True},
                {"run": make_run("r2", status="failed", token_cost=None), "cost_available": False},
            ]
        },
        "ResignableRunLogValidator": {
            "prior": chain,
            "appended": append_record(
                chain, record_id="rec3", record_type="draft",
                recorded_at="2026-08-21T09:02:00", subject_id="d1", payload={"body": "Hi"},
            ),
        },
        "AttestationDropValidator": {
            "capabilities": [],
            "claims": [],
            "scenarios": [{"name": "configuration", "success": True}, {"name": "export", "success": True}],
        },
        "SingleOperatorBoundaryValidator": {
            "scenarios": [{"name": "single_operator_create_agent", "success": True}],
            "controls": [],
        },
        "AgentSchemaValidator": {"agents": [live]},
        "RunSchemaValidator": {"runs": [run], "agents": [live]},
        "OpportunitySchemaValidator": {
            "opportunities": [opp], "runs": [run], "persons": [person],
        },
        "DraftSchemaValidator": {
            "drafts": [draft], "opportunities": [opp], "transitions": [],
        },
        "ConnectionSchemaValidator": {"connections": [make_connection()]},
        "PersonSchemaValidator": {"persons": [person]},
        "RunLogRecordSchemaValidator": {"records": chain, "subjects": ["r1", "o1", "d1"]},

        # WP-RL-002
        "ProviderTaskContractValidator": {
            "task_contracts": {
                t: {"input_shape": ["prompt"], "output_shape": ["text"]}
                for t in ("chat", "qualify", "compose")
            },
            "provider_contracts": [],
        },
        "ProviderChoiceValidator": {
            "providers": list(PROVIDERS),
            "availability": {p: True for p in PROVIDERS},
            "selections": [
                {"provider": "deepclaude", "started": True, "invocation": {"invocation_id": "i1"}, "reason": None},
            ],
        },
        "ProviderRoutingValidator": {
            "routing": {"chat": "codex", "qualify": "deepclaude", "compose": "local"},
            "dispatches": [
                {"task_type": "chat", "provider_requested": "codex", "provider_used": "codex", "evidence": {"provider": "codex"}},
                {"task_type": "qualify", "provider_requested": "deepclaude", "provider_used": "deepclaude", "evidence": {"provider": "deepclaude"}},
                {"task_type": "compose", "provider_requested": "local", "provider_used": "local", "evidence": {"provider": "local"}},
            ],
        },
        "ProviderFailureValidator": {
            "failures": [
                {"provider_requested": "codex", "status": "failed", "failure_reason": "runtime unavailable",
                 "result_ref": None, "provider_used": None, "substituted_result": False},
            ],
        },
        "ProviderSwapGateValidator": {
            "golden_set": {
                "candidate_verdicts": [{"id": "v" + str(i), "match": True} for i in range(20)],
                "voice_judged_drafts": [{"id": "d" + str(i), "passes": True} for i in range(10)],
            },
            "activation": {"activated": True, "provider": "deepclaude"},
        },
        "ProviderInvocationSchemaValidator": {
            "invocations": [make_invocation("i1")],
            "input_refs": ["in1"],
            "result_refs": ["res1"],
        },

        # WP-RL-003
        "ScheduledRunValidator": {
            "agents": [make_agent("a1", "live")],
            "triggers": [ScheduleTrigger(trigger_id="t1", agent_id="a1", due_at="2026-08-21T09:00:00", enabled=True)],
            "existing_runs": [],
            "now": "2026-08-21T09:00:00",
        },
        "RunBudgetValidator": {
            "runs": [{"run": make_run("r3", candidates_qualified=3, drafts_produced=2), "budget": default_budget()}],
        },
        "AutonomyBoundaryValidator": {
            "tasks": [
                {"name": "scan", "autonomous": True},
                {"name": "qualify", "autonomous": True},
                {"name": "draft", "autonomous": True},
                {"name": "report", "autonomous": True},
            ],
            "drafts": [],
            "outward_attempts": [],
        },
        "CadenceDefaultValidator": {
            "defaults": {"schedule": default_schedule(), "budget": default_budget()},
            "agents": [make_agent("a1", "live", mode="auto")],
            "operator_changes": [{"agent_id": "a1", "field": "mode", "after": "auto", "persisted": True}],
        },

        # WP-RL-004
        "RedditSourceBoundaryValidator": {
            "agent": make_agent("a1", "live"),
            "candidates": [candidate_auth, candidate_unauth],
            "retrieved": retrieve_authorized_candidates(make_agent("a1", "live"), [candidate_auth, candidate_unauth]),
        },
        "CandidateDeduplicationValidator": {
            "opportunities": [opp_known, opp_unknown],
            "agent_id": "a1",
        },
        "BriefQualificationValidator": {
            "qualifier": {"include": "feedback", "exclude": "promotion"},
            "candidates": [
                {"candidate_id": "cand1", "url": "https://www.reddit.com/r/SaaS/comments/inc1", "excerpt": "We need feedback on pricing."},
                {"candidate_id": "cand2", "url": "https://www.reddit.com/r/SaaS/comments/exc1", "excerpt": "promotion post here."},
            ],
            "opportunities": [make_opportunity("o5", "r1", source_url="https://www.reddit.com/r/SaaS/comments/inc1", excerpt="We need feedback on pricing.")],
        },
        "SeedKnowledgeBoundaryValidator": {
            "seed_corpus_version": "seed-v1",
            "qualification_evidence": [{"evidence_id": "e1", "seed_corpus_version": "seed-v1"}],
            "requires_corpus_edit": [],
        },
        "OptionalPersonResolutionValidator": {
            "persons": [person],
            "opportunities": [opp_known, opp_unknown],
        },

        # WP-RL-005
        "SingleDraftValidator": {
            "opportunities": [qualifying_opp],
            "budget": {"max_drafts_per_run": 3},
            "provider_used": "deepclaude",
            "drafts": compose_drafts([qualifying_opp], provider_used="deepclaude", budget={"max_drafts_per_run": 3}),
        },
        "DraftReviewContextValidator": {
            "drafts": [draft],
            "opportunities": [opp],
        },
        "ApprovalActionValidator": {
            "actions": [
                {"draft": make_draft("d_ap"), "action": "approve"},
                {"draft": make_draft("d_ea"), "action": "edit_approve", "new_body": "Edited thanks."},
                {"draft": make_draft("d_re"), "action": "regenerate", "new_body": "Fresh reply.", "new_draft_id": "d_re-regen"},
                {"draft": make_draft("d_sk"), "action": "skip"},
            ],
        },
        "NoOutboundActionValidator": {
            "outbound_actions": [],
            "network_evidence": [],
            "drafts": [draft],
            "approval_paths": [{"before": draft, "after": apply_approval_action(draft, "approve")}],
        },
        "SlopWarningValidator": {
            "cases": [{"draft": clean_draft, "flagged": False}],
        },

        # WP-RL-006
        "LiteInformationArchitectureValidator": {
            "destinations": ["chat", "agents", "approvals", "results", "settings"],
            "navigation": [],
        },
        "ChatProposalValidator": {
            "cards": [{"card_id": "c1", "editable": True, "brief_text": "Reach out to r/SaaS.", "choices": ["create_agent", "not_now"]}],
            "scenarios": [{"action": "create_agent", "created_agent": make_agent("a5", "live")}],
        },
        "AgentsScreenValidator": {
            "rows": [{
                "name": "a1", "schedule": default_schedule(), "mode": "ask", "last_run": "2026-08-21T09:00:00",
                "next_run": "2026-08-22T09:00:00", "draft_count": 2, "controls": ["pause", "edit"],
                "run_history": ["r1"], "weekly_summary": "5 surfaced, 3 drafts",
            }],
            "empty_state": None,
            "actions": [],
        },
        "ApprovalsScreenValidator": {
            "queue": [{"draft_id": "d1", "state": "pending", "actionable": True}],
            "actions": [],
        },
        "WalkingSkeletonResultsValidator": {
            "runs": [run],
            "drafts": [draft],
            "displayed": [{"id": "r1", "source": "run", "ref": "r1"}, {"id": "d1", "source": "draft", "ref": "d1"}],
            "deferred_metrics": [],
        },
        "SettingsBoundaryValidator": {
            "exposed": ["reddit_connection", "provider_routing", "run_log_export"],
            "deferred": [],
        },
        "AgentCreationTimeValidator": {
            "scenario": {"name": "creation", "elapsed_seconds": 60, "persisted_agent": make_agent("a6", "live"), "prohibited_authoring": []},
        },
        "ApprovalClearanceTimeValidator": {
            "scenario": {
                "decisions": [
                    {"draft_id": "d1", "action": "approve", "visited_other_screen": False, "result": {}},
                    {"draft_id": "d2", "action": "edit_approve", "visited_other_screen": False, "result": {}},
                    {"draft_id": "d3", "action": "regenerate", "visited_other_screen": False, "result": {}},
                    {"draft_id": "d4", "action": "skip", "visited_other_screen": False, "result": {}},
                    {"draft_id": "d5", "action": "approve", "visited_other_screen": False, "result": {}},
                ],
                "elapsed_seconds": 300,
            },
        },
    }


def run_reconciliation(fixtures: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the complete catalog against conforming fixtures and return the
    results together with a reconciliation verdict."""
    if fixtures is None:
        fixtures = build_conforming_fixtures()
    results = run_complete_catalog(fixtures)
    failed = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    return {
        "catalog_size": len(VALIDATOR_CATALOG),
        "complete_catalog_size": len(COMPLETE_VALIDATOR_CATALOG),
        "results": results,
        "passed_all": not failed,
        "failures": failed,
    }
