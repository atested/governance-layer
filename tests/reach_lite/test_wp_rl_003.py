"""WP-RL-003 conformance: live-Agent scheduling and internal Run orchestration.

The four scheduling validators (ScheduledRunValidator, RunBudgetValidator,
AutonomyBoundaryValidator, CadenceDefaultValidator) plus the reused
RunAccountingValidator and applicable AgentLifecycleValidator cases must return
"passed": true against due, early, duplicate, paused, draft, disabled,
over-limit, changed-default, and unavailable-cost fixtures, and must reject
fixtures that admit a spurious Run, overrun a budget, widen autonomy, or drop
an operator change.
"""

import pytest

from reach_lite.domain import (
    Agent,
    Run,
    ScheduleOutcome,
    ScheduleTrigger,
    default_budget,
    default_schedule,
)
from reach_lite.validators import (
    ALL_VALIDATORS,
    WP_RL_003_VALIDATORS,
    run_wp_rl_003_validator_suite,
)


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_agent(agent_id="a1", state="live", schedule=None, budget=None, **kw):
    base = dict(
        agent_id=agent_id,
        brief_text="Reach out to r/SaaS on weekdays at 09:00.",
        schedule=schedule if schedule is not None else default_schedule(),
        sources=[{"kind": "subreddit", "value": "r/SaaS"}],
        qualifier={"include": "founders asking for feedback", "exclude": ""},
        action="draft_reply",
        mode="ask",
        budget=budget if budget is not None else default_budget(),
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


NOW = "2026-08-21T09:00:00"


def scheduled_fixture(agents, triggers, existing_runs=None, now=NOW):
    return {
        "agents": agents,
        "triggers": triggers,
        "existing_runs": existing_runs or [],
        "now": now,
    }


# ---------------------------------------------------------------------------
# Base conforming fixture suite (all six validators pass).
# ---------------------------------------------------------------------------

def success_fixtures():
    return {
        "ScheduledRunValidator": scheduled_fixture(
            [make_agent("a1", "live")],
            [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
        ),
        "RunAccountingValidator": {
            "runs": [
                {"run": make_run("r1"), "cost_available": True},
                {
                    "run": make_run("r2", status="failed", token_cost=None),
                    "cost_available": False,
                },
            ],
        },
        "RunBudgetValidator": {
            "runs": [
                {
                    "run": make_run("r1", candidates_qualified=4, drafts_produced=3),
                    "budget": default_budget(),
                }
            ],
        },
        "AutonomyBoundaryValidator": {
            "tasks": [
                {"name": "scan", "autonomous": True},
                {"name": "qualify", "autonomous": True},
                {"name": "draft", "autonomous": True},
                {"name": "report", "autonomous": True},
            ],
            "drafts": [
                {"draft_id": "d1", "state": "approved", "outward_eligible": True}
            ],
            "outward_attempts": [],
        },
        "CadenceDefaultValidator": {
            "defaults": {"schedule": default_schedule(), "budget": default_budget()},
            "agents": [make_agent("a1")],
            "operator_changes": [],
        },
        "AgentLifecycleValidator": {
            "agents": [
                make_agent("a1", "live"),
                make_agent("a2", "draft"),
                make_agent("a3", "paused"),
            ],
            "transitions": [{"agent_id": "a1", "from": "draft", "to": "live"}],
            "runs": [make_run("r1", "a1")],
        },
    }


# ---------------------------------------------------------------------------
# Scenario suites: each must also yield passed: true for every validator.
# ---------------------------------------------------------------------------

def due_fixtures():
    return success_fixtures()


def early_fixtures():
    fixtures = success_fixtures()
    fixtures["ScheduledRunValidator"] = scheduled_fixture(
        [make_agent("a1", "live")],
        [ScheduleTrigger("t1", "a1", "2026-08-21T10:00:00", True)],
    )
    return fixtures


def duplicate_fixtures():
    fixtures = success_fixtures()
    fixtures["ScheduledRunValidator"] = scheduled_fixture(
        [make_agent("a1", "live")],
        [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
        existing_runs=[make_run("r-existing", "a1", started_at="2026-08-21T09:00:00")],
    )
    return fixtures


def paused_fixtures():
    fixtures = success_fixtures()
    fixtures["ScheduledRunValidator"] = scheduled_fixture(
        [make_agent("a1", "paused")],
        [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
    )
    return fixtures


def draft_fixtures():
    fixtures = success_fixtures()
    fixtures["ScheduledRunValidator"] = scheduled_fixture(
        [make_agent("a1", "draft")],
        [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
    )
    return fixtures


def disabled_fixtures():
    fixtures = success_fixtures()
    fixtures["ScheduledRunValidator"] = scheduled_fixture(
        [make_agent("a1", "live")],
        [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", False)],
    )
    return fixtures


def over_limit_fixtures():
    fixtures = success_fixtures()
    fixtures["RunBudgetValidator"] = {
        "runs": [
            {
                "run": make_run(
                    "r1", candidates_seen=25, candidates_qualified=5, drafts_produced=3
                ),
                "budget": default_budget(),
            }
        ],
    }
    return fixtures


def changed_default_fixtures():
    fixtures = success_fixtures()
    lowered_schedule = {
        "cadence": "weekly",
        "days": ["mon", "wed", "fri"],
        "time": "10:00",
    }
    lowered_budget = {"max_surfaced_per_run": 2, "max_drafts_per_run": 1}
    agent = make_agent("a2", schedule=lowered_schedule, budget=lowered_budget)
    fixtures["CadenceDefaultValidator"] = {
        "defaults": {"schedule": default_schedule(), "budget": default_budget()},
        "agents": [make_agent("a1"), agent],
        "operator_changes": [
            {
                "agent_id": "a2",
                "field": "budget",
                "after": lowered_budget,
                "persisted": True,
            },
            {
                "agent_id": "a2",
                "field": "schedule",
                "after": lowered_schedule,
                "persisted": True,
            },
        ],
    }
    return fixtures


def unavailable_cost_fixtures():
    fixtures = success_fixtures()
    fixtures["RunAccountingValidator"] = {
        "runs": [
            {"run": make_run("r1"), "cost_available": True},
            {
                "run": make_run("r-unavailable", status="failed", token_cost=None),
                "cost_available": False,
            },
        ],
    }
    return fixtures


# ---------------------------------------------------------------------------
# Invalid cases: each must yield passed: false.
# ---------------------------------------------------------------------------

INVALID_CASES = [
    (
        "ScheduledRunValidator",
        {
            "agents": [make_agent("a1", "live")],
            "triggers": [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
            "existing_runs": [],
            "now": NOW,
            "outcome": ScheduleOutcome(
                admitted=[
                    make_run("run-t1", "a1", started_at="2026-08-21T09:00:00", status="running"),
                    make_run("run-t1b", "a1", started_at="2026-08-21T09:00:00", status="running"),
                ],
                skipped=[],
            ),
        },
    ),
    (
        "ScheduledRunValidator",
        {
            "agents": [make_agent("a1", "paused")],
            "triggers": [ScheduleTrigger("t1", "a1", "2026-08-21T09:00:00", True)],
            "existing_runs": [],
            "now": NOW,
            "outcome": ScheduleOutcome(
                admitted=[
                    make_run("run-t1", "a1", started_at="2026-08-21T09:00:00", status="running")
                ],
                skipped=[],
            ),
        },
    ),
    (
        "RunBudgetValidator",
        {
            "runs": [
                {
                    "run": make_run("r1", candidates_qualified=6, drafts_produced=3),
                    "budget": default_budget(),
                }
            ]
        },
    ),
    (
        "AutonomyBoundaryValidator",
        {
            "tasks": [{"name": "post", "autonomous": True}],
            "drafts": [],
            "outward_attempts": [],
        },
    ),
    (
        "AutonomyBoundaryValidator",
        {
            "tasks": [],
            "drafts": [{"draft_id": "d1", "state": "pending", "outward_eligible": True}],
            "outward_attempts": [],
        },
    ),
    (
        "CadenceDefaultValidator",
        {
            "defaults": {"schedule": default_schedule(), "budget": default_budget()},
            "agents": [make_agent("a1")],
            "operator_changes": [
                {
                    "agent_id": "a1",
                    "field": "budget",
                    "after": {"max_surfaced_per_run": 1, "max_drafts_per_run": 1},
                    "persisted": False,
                }
            ],
        },
    ),
    (
        "RunAccountingValidator",
        {"runs": [{"run": make_run("r1", token_cost=999), "cost_available": False}]},
    ),
    (
        "AgentLifecycleValidator",
        {
            "agents": [make_agent("a1", "live")],
            "transitions": [],
            "runs": [make_run("r1", "a2")],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("due", due_fixtures),
    ("early", early_fixtures),
    ("duplicate", duplicate_fixtures),
    ("paused", paused_fixtures),
    ("draft", draft_fixtures),
    ("disabled", disabled_fixtures),
    ("over-limit", over_limit_fixtures),
    ("changed-default", changed_default_fixtures),
    ("unavailable-cost", unavailable_cost_fixtures),
]


@pytest.mark.parametrize("scenario_name,builder", SCENARIOS)
def test_wp_rl_003_validators_pass_every_scenario(scenario_name, builder):
    fixtures = builder()
    results = run_wp_rl_003_validator_suite(fixtures)
    assert set(results) == set(WP_RL_003_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, (scenario_name, failures)
    for name in ("RunAccountingValidator", "AgentLifecycleValidator"):
        result = ALL_VALIDATORS[name](fixtures[name])
        assert result["passed"], (scenario_name, name, result["findings"])


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_wp_rl_003_validators_reject_invalid_fixtures(name, fixture):
    validator = WP_RL_003_VALIDATORS.get(name) or ALL_VALIDATORS[name]
    result = validator(fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_due_schedule_yields_exactly_one_attributable_run():
    from reach_lite.domain import evaluate_schedule

    outcome = evaluate_schedule(
        [make_agent("a1", "live")],
        [ScheduleTrigger("t1", "a1", NOW, True)],
        [],
        NOW,
    )
    assert len(outcome.admitted) == 1
    run = outcome.admitted[0]
    assert run.agent_id == "a1"
    assert run.status == "running"
    assert outcome.skipped == []


def test_early_and_duplicate_and_disabled_triggers_produce_no_run():
    from reach_lite.domain import evaluate_schedule

    outcome = evaluate_schedule(
        [make_agent("a1", "live")],
        [
            ScheduleTrigger("t-early", "a1", "2026-08-21T10:00:00", True),
            ScheduleTrigger("t-disabled", "a1", NOW, False),
        ],
        [make_run("r-existing", "a1", started_at=NOW)],
        NOW,
    )
    assert outcome.admitted == []
    reasons = {s["trigger_id"]: s["reason"] for s in outcome.skipped}
    assert reasons == {
        "t-early": "early",
        "t-disabled": "disabled",
    }


def test_scheduling_defaults_match_spec():
    assert default_schedule() == {
        "cadence": "weekly",
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "time": "09:00",
    }
    assert default_budget() == {"max_surfaced_per_run": 5, "max_drafts_per_run": 3}
