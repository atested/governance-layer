"""WP-RL-006 conformance: five-destination lite operator experience.

The eleven validators (LiteInformationArchitectureValidator, ChatProposalValidator,
AgentsScreenValidator, ApprovalsScreenValidator, WalkingSkeletonResultsValidator,
SettingsBoundaryValidator, AgentCreationTimeValidator, ApprovalClearanceTimeValidator,
BriefOnlyAuthoringValidator, CadenceDefaultValidator, NoOutboundActionValidator)
must return "passed": true against populated, empty, deferred, Create, Not now,
all-approval-action, and timed fixtures, and must reject fixtures that restore the
analyst control room, fabricate deferred evidence, add prohibited authoring, or
exceed the timed operator paths.
"""

import pytest

from reach_lite.domain import (
    Agent,
    Draft,
    Opportunity,
    Run,
    default_budget,
    default_schedule,
    new_agent,
)
from reach_lite.validators import (
    WP_RL_006_VALIDATORS,
    run_wp_rl_006_validator_suite,
)


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_agent(agent_id="a1", state="live", **kw):
    agent = new_agent(
        agent_id,
        "Discuss pricing with founders on r/SaaS, weekdays.",
        [{"kind": "subreddit", "value": "r/SaaS"}],
        {"include": "feedback", "exclude": "promotion"},
    )
    agent.state = state
    for key, value in kw.items():
        setattr(agent, key, value)
    return agent


def make_run(run_id="r1", agent_id="a1", **kw):
    base = dict(
        run_id=run_id,
        agent_id=agent_id,
        started_at="2026-08-21T09:00:00",
        finished_at="2026-08-21T09:05:00",
        sources_polled=["r/SaaS"],
        candidates_seen=10,
        candidates_qualified=5,
        drafts_produced=3,
        provider_used="deepclaude",
        token_cost=1234,
        status="succeeded",
    )
    base.update(kw)
    return Run(**base)


def make_draft(draft_id="d1", opportunity_id="o1", state="pending", **kw):
    base = dict(
        draft_id=draft_id,
        opportunity_id=opportunity_id,
        body="Thanks for the specifics on your pricing.",
        channel="reddit",
        target_url="https://reddit.com/r/SaaS/comments/abc",
        provider_used="deepclaude",
        attribution_link=None,
        state=state,
    )
    base.update(kw)
    return Draft(**base)


def agent_screen_row(name="a1"):
    return {
        "name": name,
        "schedule": default_schedule(),
        "mode": "ask",
        "last_run": "2026-08-21T09:00:00",
        "next_run": "2026-08-24T09:00:00",
        "draft_count": 3,
        "controls": ["pause", "edit"],
        "run_history": ["r1"],
        "weekly_summary": "5 surfaced, 3 drafts.",
    }


CLEAN_BODY = "Appreciate the specifics on your pricing tiers. Here is what we would change."


# ---------------------------------------------------------------------------
# Base conforming fixture suite (all eleven validators pass).
# ---------------------------------------------------------------------------

def success_fixtures():
    return {
        "LiteInformationArchitectureValidator": {
            "destinations": ["chat", "agents", "approvals", "results", "settings"],
            "navigation": ["chat", "agents", "approvals", "results", "settings"],
        },
        "ChatProposalValidator": {
            "cards": [
                {
                    "card_id": "c1",
                    "brief_text": "Discuss pricing with founders on r/SaaS.",
                    "editable": True,
                    "choices": ["create_agent", "not_now"],
                },
            ],
            "scenarios": [
                {"action": "create_agent", "created_agent": make_agent("a1", state="draft")},
                {"action": "not_now", "created_agent": None},
            ],
        },
        "AgentsScreenValidator": {
            "rows": [agent_screen_row("a1"), agent_screen_row("a2")],
            "empty_state": "",
            "actions": [
                {"name": "a1", "action": "pause", "result": {"state": "paused"}},
                {"name": "a2", "action": "edit", "result": {"state": "draft"}},
            ],
        },
        "ApprovalsScreenValidator": {
            "queue": [
                {"draft_id": "d1", "state": "pending"},
                {"draft_id": "d2", "state": "pending"},
            ],
            "actions": [
                {"draft_id": "d1", "action": "approve", "result": make_draft("d1", state="approved"), "visited_other_screen": False},
                {"draft_id": "d2", "action": "skip", "result": make_draft("d2", state="rejected"), "visited_other_screen": False},
            ],
        },
        "WalkingSkeletonResultsValidator": {
            "runs": [make_run("r1")],
            "drafts": [make_draft("d1", state="approved")],
            "displayed": [
                {"id": "row-1", "source": "run", "ref": "r1"},
                {"id": "row-2", "source": "draft", "ref": "d1"},
            ],
            "deferred_metrics": [
                "posting: unavailable",
                "engagement: unavailable",
                "click: unavailable",
                "download: unavailable",
            ],
        },
        "SettingsBoundaryValidator": {
            "exposed": ["reddit_connection", "provider_routing", "run_log_export"],
            "deferred": [
                {"name": "website_voice_derivation", "available": False},
                {"name": "linkedin", "available": False},
                {"name": "x_posting", "available": False},
                {"name": "substack", "available": False},
                {"name": "website_analysis", "available": False},
            ],
        },
        "AgentCreationTimeValidator": {
            "scenario": {
                "name": "creation",
                "elapsed_seconds": 45,
                "persisted_agent": make_agent("a1", state="live"),
                "prohibited_authoring": [],
            },
        },
        "ApprovalClearanceTimeValidator": {
            "scenario": {
                "elapsed_seconds": 240,
                "decisions": [
                    {"draft_id": "d1", "action": "approve", "result": make_draft("d1", state="approved"), "visited_other_screen": False},
                    {"draft_id": "d2", "action": "edit_approve", "result": make_draft("d2", state="edited"), "visited_other_screen": False},
                    {"draft_id": "d3", "action": "regenerate", "result": make_draft("d3-regen", state="pending"), "visited_other_screen": False},
                    {"draft_id": "d4", "action": "skip", "result": make_draft("d4", state="rejected"), "visited_other_screen": False},
                    {"draft_id": "d5", "action": "approve", "result": make_draft("d5", state="approved"), "visited_other_screen": False},
                ],
            },
        },
        "BriefOnlyAuthoringValidator": {
            "persisted_agent": make_agent("a1", state="live"),
            "prohibited_authoring": [],
        },
        "CadenceDefaultValidator": {
            "defaults": {"schedule": default_schedule(), "budget": default_budget()},
            "agents": [make_agent("a1")],
            "operator_changes": [],
        },
        "NoOutboundActionValidator": {
            "outbound_actions": [],
            "network_evidence": [],
            "drafts": [make_draft("d1", state="approved")],
            "approval_paths": [],
        },
    }


# ---------------------------------------------------------------------------
# Scenario suites: each must also yield passed: true for every validator.
# ---------------------------------------------------------------------------

def populated_fixtures():
    fixtures = success_fixtures()
    fixtures["AgentsScreenValidator"] = {
        "rows": [agent_screen_row("a1"), agent_screen_row("a2"), agent_screen_row("a3")],
        "empty_state": "",
        "actions": [],
    }
    return fixtures


def empty_fixtures():
    fixtures = success_fixtures()
    fixtures["AgentsScreenValidator"] = {
        "rows": [],
        "empty_state": "No Agents yet. Create one from Chat.",
        "actions": [],
    }
    fixtures["ApprovalsScreenValidator"] = {
        "queue": [],
        "actions": [],
    }
    return fixtures


def deferred_fixtures():
    fixtures = success_fixtures()
    fixtures["WalkingSkeletonResultsValidator"] = {
        "runs": [make_run("r1")],
        "drafts": [make_draft("d1", state="approved")],
        "displayed": [{"id": "row-1", "source": "run", "ref": "r1"}],
        "deferred_metrics": [
            "posting: unavailable", "engagement: deferred",
            "click: unavailable", "download: deferred",
        ],
    }
    fixtures["SettingsBoundaryValidator"] = {
        "exposed": ["reddit_connection", "provider_routing", "run_log_export"],
        "deferred": [
            {"name": "website_voice_derivation", "available": False},
            {"name": "linkedin", "available": False},
            {"name": "x_posting", "available": False},
            {"name": "substack", "available": False},
            {"name": "website_analysis", "available": False},
        ],
    }
    return fixtures


def create_scenario_fixtures():
    fixtures = success_fixtures()
    fixtures["ChatProposalValidator"] = {
        "cards": [
            {
                "card_id": "c1",
                "brief_text": "Discuss pricing with founders on r/SaaS.",
                "editable": True,
                "choices": ["create_agent", "not_now"],
            },
        ],
        "scenarios": [{"action": "create_agent", "created_agent": make_agent("a1", state="draft")}],
    }
    return fixtures


def not_now_scenario_fixtures():
    fixtures = success_fixtures()
    fixtures["ChatProposalValidator"] = {
        "cards": [
            {
                "card_id": "c1",
                "brief_text": "Discuss pricing with founders on r/SaaS.",
                "editable": True,
                "choices": ["create_agent", "not_now"],
            },
        ],
        "scenarios": [{"action": "not_now", "created_agent": None}],
    }
    return fixtures


def all_approval_actions_fixtures():
    fixtures = success_fixtures()
    fixtures["ApprovalsScreenValidator"] = {
        "queue": [
            {"draft_id": "d1", "state": "pending"},
            {"draft_id": "d2", "state": "pending"},
            {"draft_id": "d3", "state": "pending"},
            {"draft_id": "d4", "state": "pending"},
        ],
        "actions": [
            {"draft_id": "d1", "action": "approve", "result": make_draft("d1", state="approved"), "visited_other_screen": False},
            {"draft_id": "d2", "action": "edit_approve", "result": make_draft("d2", state="edited"), "visited_other_screen": False},
            {"draft_id": "d3", "action": "regenerate", "result": make_draft("d3-regen", state="pending"), "visited_other_screen": False},
            {"draft_id": "d4", "action": "skip", "result": make_draft("d4", state="rejected"), "visited_other_screen": False},
        ],
    }
    return fixtures


def timed_fixtures():
    fixtures = success_fixtures()
    fixtures["AgentCreationTimeValidator"] = {
        "scenario": {
            "name": "creation",
            "elapsed_seconds": 30,
            "persisted_agent": make_agent("a1", state="live"),
            "prohibited_authoring": [],
        },
    }
    fixtures["ApprovalClearanceTimeValidator"] = {
        "scenario": {
            "elapsed_seconds": 300,
            "decisions": [
                {"draft_id": "d1", "action": "approve", "result": make_draft("d1", state="approved"), "visited_other_screen": False},
                {"draft_id": "d2", "action": "edit_approve", "result": make_draft("d2", state="edited"), "visited_other_screen": False},
                {"draft_id": "d3", "action": "regenerate", "result": make_draft("d3-regen", state="pending"), "visited_other_screen": False},
                {"draft_id": "d4", "action": "skip", "result": make_draft("d4", state="rejected"), "visited_other_screen": False},
                {"draft_id": "d5", "action": "approve", "result": make_draft("d5", state="approved"), "visited_other_screen": False},
            ],
        },
    }
    return fixtures


# ---------------------------------------------------------------------------
# Invalid cases: each must yield passed: false.
# ---------------------------------------------------------------------------

INVALID_CASES = [
    (
        "LiteInformationArchitectureValidator",
        {
            "destinations": ["chat", "agents", "results", "settings"],
            "navigation": ["chat", "agents", "results", "settings", "pattern_editor"],
        },
    ),
    (
        "ChatProposalValidator",
        {
            "cards": [{"card_id": "c1", "brief_text": "", "editable": True, "choices": ["not_now"]}],
            "scenarios": [],
        },
    ),
    (
        "AgentsScreenValidator",
        {
            "rows": [{"name": "a1", "schedule": default_schedule(), "mode": "ask"}],
            "empty_state": "",
            "actions": [],
        },
    ),
    (
        "ApprovalsScreenValidator",
        {
            "queue": [{"draft_id": "d1", "state": "approved", "actionable": True}],
            "actions": [],
        },
    ),
    (
        "WalkingSkeletonResultsValidator",
        {
            "runs": [make_run("r1")],
            "drafts": [],
            "displayed": [{"id": "row-1", "source": "run", "ref": "r1"}, {"id": "row-2", "source": "draft", "ref": "missing"}],
            "deferred_metrics": [],
        },
    ),
    (
        "WalkingSkeletonResultsValidator",
        {
            "runs": [make_run("r1")],
            "drafts": [],
            "displayed": [],
            "deferred_metrics": ["posting: 12 posts published"],
        },
    ),
    (
        "SettingsBoundaryValidator",
        {
            "exposed": ["reddit_connection", "provider_routing"],
            "deferred": [],
        },
    ),
    (
        "SettingsBoundaryValidator",
        {
            "exposed": ["reddit_connection", "provider_routing", "run_log_export"],
            "deferred": [{"name": "linkedin", "available": True}],
        },
    ),
    (
        "AgentCreationTimeValidator",
        {
            "scenario": {
                "name": "creation",
                "elapsed_seconds": 180,
                "persisted_agent": make_agent("a1", state="live"),
                "prohibited_authoring": [],
            },
        },
    ),
    (
        "ApprovalClearanceTimeValidator",
        {
            "scenario": {
                "elapsed_seconds": 700,
                "decisions": [
                    {"draft_id": "d1", "action": "approve", "result": make_draft("d1", state="approved"), "visited_other_screen": False},
                    {"draft_id": "d2", "action": "approve", "result": make_draft("d2", state="approved"), "visited_other_screen": False},
                    {"draft_id": "d3", "action": "approve", "result": make_draft("d3", state="approved"), "visited_other_screen": False},
                    {"draft_id": "d4", "action": "approve", "result": make_draft("d4", state="approved"), "visited_other_screen": False},
                    {"draft_id": "d5", "action": "approve", "result": make_draft("d5", state="approved"), "visited_other_screen": False},
                ],
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("populated", populated_fixtures),
    ("empty", empty_fixtures),
    ("deferred", deferred_fixtures),
    ("create", create_scenario_fixtures),
    ("not-now", not_now_scenario_fixtures),
    ("all-approval-actions", all_approval_actions_fixtures),
    ("timed", timed_fixtures),
]


@pytest.mark.parametrize("scenario_name,builder", SCENARIOS)
def test_wp_rl_006_validators_pass_every_scenario(scenario_name, builder):
    fixtures = builder()
    results = run_wp_rl_006_validator_suite(fixtures)
    assert set(results) == set(WP_RL_006_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, (scenario_name, failures)


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_wp_rl_006_validators_reject_invalid_fixtures(name, fixture):
    validator = WP_RL_006_VALIDATORS[name]
    result = validator(fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_success_fixtures_cover_every_validator():
    fixtures = success_fixtures()
    assert set(fixtures) == set(WP_RL_006_VALIDATORS)
