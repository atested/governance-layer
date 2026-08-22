"""WP-RL-001 conformance: every validator passes conforming fixtures and
rejects invalid fixtures. The durable acceptance criterion is that all fifteen
named validators return "passed": true against conforming fixtures.
"""

from dataclasses import replace

import pytest

from reach_lite.domain import (
    Agent,
    Connection,
    Draft,
    Opportunity,
    Person,
    Run,
    append_record,
    default_schedule,
    interpret_brief,
    transition_agent,
)
from reach_lite.validators import ALL_VALIDATORS, run_validator_suite


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_agent(agent_id="a1", state="live", **kw):
    base = dict(
        agent_id=agent_id,
        brief_text="Reach out to r/SaaS on weekdays at 09:00.",
        schedule={"cadence": "weekly", "days": ["mon", "tue", "wed", "thu", "fri"], "time": "09:00"},
        sources=[{"kind": "subreddit", "value": "r/SaaS"}],
        qualifier={"include": "founders asking for feedback", "exclude": ""},
        action="draft_reply",
        mode="ask",
        budget={"max_surfaced_per_run": 5, "max_drafts_per_run": 3},
        state=state,
    )
    base.update(kw)
    return Agent(**base)


def make_run(run_id="r1", agent_id="a1", **kw):
    base = dict(
        run_id=run_id,
        agent_id=agent_id,
        started_at="2026-08-21T09:00:00",
        finished_at="2026-08-21T09:05:00",
        sources_polled=["r/SaaS"],
        candidates_seen=10,
        candidates_qualified=4,
        drafts_produced=3,
        provider_used="deepclaude",
        token_cost=1234,
        status="succeeded",
    )
    base.update(kw)
    return Run(**base)


def make_opportunity(opportunity_id="o1", run_id="r1", **kw):
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


def make_draft(draft_id="d1", opportunity_id="o1", **kw):
    base = dict(
        draft_id=draft_id,
        opportunity_id=opportunity_id,
        body="Hi, happy to share some feedback.",
        channel="reddit",
        target_url="https://www.reddit.com/r/SaaS/comments/abc123",
        provider_used="deepclaude",
        attribution_link=None,
        state="pending",
    )
    base.update(kw)
    return Draft(**base)


def make_connection(connection_id="c1", **kw):
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


def make_person(person_id="p1", **kw):
    base = dict(
        person_id=person_id,
        handles=[{"channel": "reddit", "handle": "u_alice"}],
        first_seen="2026-08-01T00:00:00",
        interactions=[{"source": "opportunity", "ref": "o1"}],
        notes="",
    )
    base.update(kw)
    return Person(**base)


def make_chain():
    chain = []
    chain = append_record(
        chain, record_id="rec1", record_type="run", recorded_at="2026-08-21T09:00:00",
        subject_id="r1", payload={"status": "succeeded"},
    )
    chain = append_record(
        chain, record_id="rec2", record_type="opportunity", recorded_at="2026-08-21T09:01:00",
        subject_id="o1", payload={"score": 0.8},
    )
    return chain


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
# Conforming and invalid fixtures.
# ---------------------------------------------------------------------------

CONFORMING = {
    "AgentAtomValidator": {
        "routes": ["chat", "agents", "approvals", "results", "settings"],
        "pipeline_controls": [],
        "agents": [make_agent()],
    },
    "BriefOnlyAuthoringValidator": {
        "persisted_agent": make_agent(state="live"),
        "prohibited_authoring": [],
    },
    "BriefInterpretationValidator": {
        "scenarios": [
            {
                "brief": WORKED_BRIEF,
                "interpreted": interpret_brief(WORKED_BRIEF)[0],
                "clarifications": interpret_brief(WORKED_BRIEF)[1],
                "expected": WORKED_EXPECTED,
                "required_missing": [],
            }
        ]
    },
    "AgentLifecycleValidator": {
        "agents": [make_agent("a1", "live"), make_agent("a2", "draft"), make_agent("a3", "paused")],
        "transitions": [{"agent_id": "a1", "from": "draft", "to": "live"}],
        "runs": [make_run("r1", "a1")],
    },
    "RunAccountingValidator": {
        "runs": [
            {"run": make_run("r1"), "cost_available": True},
            {"run": make_run("r2", status="failed", token_cost=None), "cost_available": False},
        ]
    },
    "ResignableRunLogValidator": {
        "prior": make_chain(),
        "appended": append_record(
            make_chain(), record_id="rec3", record_type="draft", recorded_at="2026-08-21T09:02:00",
            subject_id="d1", payload={"body": "Hi"},
        ),
    },
    "AttestationDropValidator": {
        "capabilities": [],
        "claims": [],
        "scenarios": [
            {"name": "configuration", "success": True},
            {"name": "export", "success": True},
        ],
    },
    "SingleOperatorBoundaryValidator": {
        "scenarios": [{"name": "single_operator_create_agent", "success": True}],
        "controls": [],
    },
    "AgentSchemaValidator": {"agents": [make_agent()]},
    "RunSchemaValidator": {"runs": [make_run()], "agents": [make_agent()]},
    "OpportunitySchemaValidator": {
        "opportunities": [make_opportunity()],
        "runs": [make_run()],
        "persons": [make_person()],
    },
    "DraftSchemaValidator": {
        "drafts": [make_draft()],
        "opportunities": [make_opportunity()],
        "transitions": [],
    },
    "ConnectionSchemaValidator": {"connections": [make_connection()]},
    "PersonSchemaValidator": {"persons": [make_person()]},
    "RunLogRecordSchemaValidator": {
        "records": make_chain(),
        "subjects": ["r1", "o1", "d1"],
    },
}

INVALID_CASES = [
    ("AgentAtomValidator", {
        "routes": ["chat", "agents"],
        "pipeline_controls": ["decision_pipeline"],
        "agents": [make_agent()],
    }),
    ("BriefOnlyAuthoringValidator", {
        "persisted_agent": make_agent(state="live"),
        "prohibited_authoring": ["yaml_authoring"],
    }),
    ("BriefInterpretationValidator", {
        "scenarios": [{
            "brief": "Reach out to people on Reddit.",
            "interpreted": {
                "schedule": default_schedule(),
                "sources": [],
                "qualifier": {"include": "", "exclude": ""},
                "action": "draft_reply",
                "budget": {"max_surfaced_per_run": 5, "max_drafts_per_run": 3},
            },
            "clarifications": ["schedule cadence not specified"],
            "expected": None,
            "required_missing": ["schedule", "sources", "qualifier"],
        }]
    }),
    ("AgentLifecycleValidator", {
        "agents": [make_agent("a1", "live")],
        "transitions": [{"agent_id": "a1", "from": "live", "to": "archived"}],
        "runs": [],
    }),
    ("RunAccountingValidator", {
        "runs": [{"run": make_run("r1", token_cost=999), "cost_available": False}]
    }),
    ("ResignableRunLogValidator", {
        "prior": make_chain(),
        "appended": [replace(make_chain()[0], payload={"status": "tampered"}), make_chain()[1]],
    }),
    ("AttestationDropValidator", {
        "capabilities": ["signatures"],
        "claims": [],
        "scenarios": [{"name": "export", "success": True}],
    }),
    ("SingleOperatorBoundaryValidator", {
        "scenarios": [{"name": "solo", "success": True}],
        "controls": ["billing"],
    }),
    ("AgentSchemaValidator", {"agents": [make_agent(state="archived")]}),
    ("RunSchemaValidator", {"runs": [make_run(agent_id="missing")], "agents": [make_agent()]}),
    ("OpportunitySchemaValidator", {
        "opportunities": [make_opportunity(qualify_score=1.5)],
        "runs": [make_run()],
        "persons": [make_person()],
    }),
    ("DraftSchemaValidator", {
        "drafts": [make_draft(attribution_link="https://example.com")],
        "opportunities": [make_opportunity()],
        "transitions": [],
    }),
    ("ConnectionSchemaValidator", {"connections": [make_connection(status="unknown")]}),
    ("PersonSchemaValidator", {"persons": [make_person(handles=[])]}),
    ("RunLogRecordSchemaValidator", {
        "records": [replace(make_chain()[0], payload={"status": "tampered"}), make_chain()[1]],
        "subjects": ["r1", "o1"],
    }),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(ALL_VALIDATORS))
def test_every_validator_passes_conforming_fixture(name):
    result = ALL_VALIDATORS[name](CONFORMING[name])
    assert result["passed"] is True, (name, result["findings"])


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_validators_reject_invalid_fixtures(name, fixture):
    result = ALL_VALIDATORS[name](fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_full_suite_returns_passed_true_for_every_validator():
    results = run_validator_suite(CONFORMING)
    assert set(results) == set(ALL_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, failures


def test_agent_lifecycle_transition_helper():
    agent = make_agent(state="draft")
    live = transition_agent(agent, "live")
    assert live is not None and live.state == "live"
    assert transition_agent(agent, "archived") is None
