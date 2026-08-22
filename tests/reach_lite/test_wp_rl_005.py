"""WP-RL-005 conformance: composition, advisory slop review, and local approval.

The eight validators (SingleDraftValidator, DraftReviewContextValidator,
ApprovalActionValidator, NoOutboundActionValidator, AutonomyBoundaryValidator,
SlopWarningValidator, DraftSchemaValidator, RunBudgetValidator) must return
"passed": true against qualifying/non-qualifying, over-budget, flagged/unflagged,
each-approval-action, and outbound-attempt fixtures, and must reject fixtures that
produce multiple Draft options, hide review context, misapply an approval action,
emit an outward action, let a slop warning gate, or overrun the draft budget.
"""

import pytest

from reach_lite.domain import (
    Draft,
    Opportunity,
    Run,
    apply_approval_action,
    compose_drafts,
    default_budget,
    draft_review_context,
    evaluate_slop,
)
from reach_lite.validators import (
    WP_RL_005_VALIDATORS,
    run_wp_rl_005_validator_suite,
)


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_opportunity(opportunity_id="o1", run_id="r1", **kw):
    base = dict(
        opportunity_id=opportunity_id,
        run_id=run_id,
        channel="reddit",
        source_url="https://reddit.com/r/SaaS/comments/abc",
        author_handle="alice",
        excerpt="Founders asking for feedback on pricing.",
        qualify_score=0.75,
        qualify_reason="matches inclusion intent: feedback",
        person_id=None,
    )
    base.update(kw)
    return Opportunity(**base)


def make_draft(draft_id="d1", opportunity_id="o1", body="Thanks for the feedback.", **kw):
    base = dict(
        draft_id=draft_id,
        opportunity_id=opportunity_id,
        body=body,
        channel="reddit",
        target_url="https://reddit.com/r/SaaS/comments/abc",
        provider_used="deepclaude",
        attribution_link=None,
        state="pending",
    )
    base.update(kw)
    return Draft(**base)


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


CLEAN_BODY = "Appreciate the specifics on your pricing tiers. Here is what we would change."
SLOP_BODY = "In today's rapidly evolving landscape, we leverage synergies to empower you."


# ---------------------------------------------------------------------------
# Base conforming fixture suite (all eight validators pass).
# ---------------------------------------------------------------------------

def success_fixtures():
    opp1 = make_opportunity("o1")
    opp2 = make_opportunity(
        "o2", source_url="https://reddit.com/r/SaaS/comments/def",
        qualify_reason="matches inclusion intent: feedback",
    )
    d1 = make_draft("d1", "o1", body=CLEAN_BODY)
    d2 = make_draft("d2", "o2", body=CLEAN_BODY)
    return {
        "SingleDraftValidator": {
            "opportunities": [opp1, opp2],
            "budget": default_budget(),
            "provider_used": "deepclaude",
        },
        "DraftReviewContextValidator": {
            "drafts": [d1, d2],
            "opportunities": [opp1, opp2],
        },
        "ApprovalActionValidator": {
            "actions": [
                {"draft": make_draft("a1", "o1", body=CLEAN_BODY), "action": "approve"},
                {
                    "draft": make_draft("a2", "o1", body=CLEAN_BODY),
                    "action": "edit_approve",
                    "new_body": "Edited reply body.",
                },
                {
                    "draft": make_draft("a3", "o2", body=CLEAN_BODY),
                    "action": "regenerate",
                    "new_body": "Fresh reply body.",
                    "new_draft_id": "a3-regen",
                },
                {"draft": make_draft("a4", "o2", body=CLEAN_BODY), "action": "skip"},
            ],
        },
        "NoOutboundActionValidator": {
            "outbound_actions": [],
            "network_evidence": [],
            "drafts": [
                make_draft("d1", "o1", body=CLEAN_BODY, state="approved"),
                make_draft("d2", "o2", body=CLEAN_BODY, state="rejected"),
            ],
            "approval_paths": [
                {
                    "before": make_draft("d1", "o1", body=CLEAN_BODY, state="pending"),
                    "after": make_draft("d1", "o1", body=CLEAN_BODY, state="approved"),
                },
                {
                    "before": make_draft("d2", "o2", body=CLEAN_BODY, state="pending"),
                    "after": make_draft("d2", "o2", body=CLEAN_BODY, state="rejected"),
                },
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
                {"draft_id": "d1", "state": "pending", "outward_eligible": False},
                {"draft_id": "d2", "state": "approved", "outward_eligible": False},
            ],
            "outward_attempts": [],
        },
        "SlopWarningValidator": {
            "cases": [
                {"draft": make_draft("s1", "o1", body=CLEAN_BODY), "flagged": False},
                {"draft": make_draft("s2", "o2", body=SLOP_BODY), "flagged": True},
            ],
        },
        "DraftSchemaValidator": {
            "drafts": [d1, d2],
            "opportunities": [opp1, opp2],
            "transitions": [],
        },
        "RunBudgetValidator": {
            "runs": [
                {
                    "run": make_run("r1", candidates_qualified=5, drafts_produced=3),
                    "budget": default_budget(),
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Scenario suites: each must also yield passed: true for every validator.
# ---------------------------------------------------------------------------

def qualifying_nonqualifying_fixtures():
    fixtures = success_fixtures()
    opp1 = make_opportunity("o1")
    opp2 = make_opportunity(
        "o2", source_url="https://reddit.com/r/SaaS/comments/def",
        qualify_reason="matches inclusion intent: feedback",
    )
    fixtures["SingleDraftValidator"] = {
        "opportunities": [opp1, opp2],
        "budget": default_budget(),
        "provider_used": "local",
    }
    fixtures["DraftReviewContextValidator"] = {
        "drafts": [make_draft("d1", "o1"), make_draft("d2", "o2")],
        "opportunities": [opp1, opp2],
    }
    return fixtures


def over_budget_fixtures():
    fixtures = success_fixtures()
    opps = [
        make_opportunity(
            oid,
            source_url="https://reddit.com/r/SaaS/comments/" + oid,
        )
        for oid in ("o1", "o2", "o3")
    ]
    # Budget caps drafts at 1; composition must stop rather than exceed.
    fixtures["SingleDraftValidator"] = {
        "opportunities": opps,
        "budget": {"max_surfaced_per_run": 5, "max_drafts_per_run": 1},
        "provider_used": "deepclaude",
    }
    fixtures["RunBudgetValidator"] = {
        "runs": [
            {
                "run": make_run("r1", candidates_qualified=5, drafts_produced=3),
                "budget": default_budget(),
            }
        ]
    }
    return fixtures


def flagged_unflagged_fixtures():
    fixtures = success_fixtures()
    fixtures["SlopWarningValidator"] = {
        "cases": [
            {"draft": make_draft("s1", "o1", body=CLEAN_BODY), "flagged": False},
            {"draft": make_draft("s2", "o2", body=SLOP_BODY), "flagged": True},
            {"draft": make_draft("s3", "o1", body="Short, concrete reply."), "flagged": False},
        ],
    }
    return fixtures


def each_approval_action_fixtures():
    fixtures = success_fixtures()
    fixtures["ApprovalActionValidator"] = {
        "actions": [
            {"draft": make_draft("a1", "o1", body=CLEAN_BODY), "action": "approve"},
            {
                "draft": make_draft("a2", "o1", body=CLEAN_BODY),
                "action": "edit_approve",
                "new_body": "Edited and accepted body.",
            },
            {
                "draft": make_draft("a3", "o2", body=SLOP_BODY),
                "action": "regenerate",
                "new_body": CLEAN_BODY,
                "new_draft_id": "a3-r2",
            },
            {"draft": make_draft("a4", "o2", body=CLEAN_BODY), "action": "skip"},
        ],
    }
    return fixtures


def outbound_attempt_fixtures():
    fixtures = success_fixtures()
    # An operator attempts to post an unapproved Draft; the system blocks it,
    # so no outward action is recorded and no Draft reaches posted.
    fixtures["NoOutboundActionValidator"] = {
        "outbound_actions": [],
        "network_evidence": [],
        "drafts": [
            make_draft("d1", "o1", body=CLEAN_BODY, state="pending"),
            make_draft("d2", "o2", body=CLEAN_BODY, state="approved"),
        ],
        "approval_paths": [
            {
                "before": make_draft("d1", "o1", body=CLEAN_BODY, state="pending"),
                "after": make_draft("d1", "o1", body=CLEAN_BODY, state="pending"),
            },
        ],
    }
    fixtures["AutonomyBoundaryValidator"] = {
        "tasks": [
            {"name": "scan", "autonomous": True},
            {"name": "qualify", "autonomous": True},
            {"name": "draft", "autonomous": True},
            {"name": "report", "autonomous": True},
        ],
        "drafts": [
            {"draft_id": "d1", "state": "pending", "outward_eligible": False},
        ],
        "outward_attempts": [],
    }
    return fixtures


# ---------------------------------------------------------------------------
# Invalid cases: each must yield passed: false.
# ---------------------------------------------------------------------------

INVALID_CASES = [
    (
        "SingleDraftValidator",
        {
            "opportunities": [make_opportunity("o1")],
            "budget": default_budget(),
            "provider_used": "deepclaude",
            "drafts": [
                make_draft("d1", "o1"),
                make_draft("d2", "o1"),
            ],
        },
    ),
    (
        "DraftReviewContextValidator",
        {
            "drafts": [make_draft("d1", "o1", body="")],
            "opportunities": [make_opportunity("o1")],
        },
    ),
    (
        "ApprovalActionValidator",
        {
            "actions": [
                {
                    "draft": make_draft("a1", "o1", body=CLEAN_BODY),
                    "action": "approve",
                    "result": make_draft("a1", "o1", body=CLEAN_BODY, state="pending"),
                },
            ],
        },
    ),
    (
        "NoOutboundActionValidator",
        {
            "outbound_actions": [],
            "network_evidence": [],
            "drafts": [make_draft("d1", "o1", state="posted")],
            "approval_paths": [],
        },
    ),
    (
        "AutonomyBoundaryValidator",
        {
            "tasks": [],
            "drafts": [],
            "outward_attempts": [{"draft_id": "d1", "channel": "reddit", "kind": "post"}],
        },
    ),
    (
        "SlopWarningValidator",
        {
            "cases": [
                {"draft": make_draft("s1", "o1", body=CLEAN_BODY), "flagged": True},
            ],
        },
    ),
    (
        "DraftSchemaValidator",
        {
            "drafts": [
                make_draft("d1", "o1", attribution_link="https://reddit.com/comment/1"),
            ],
            "opportunities": [make_opportunity("o1")],
            "transitions": [],
        },
    ),
    (
        "RunBudgetValidator",
        {
            "runs": [
                {
                    "run": make_run("r1", candidates_qualified=5, drafts_produced=4),
                    "budget": default_budget(),
                }
            ]
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("qualifying-nonqualifying", qualifying_nonqualifying_fixtures),
    ("over-budget", over_budget_fixtures),
    ("flagged-unflagged", flagged_unflagged_fixtures),
    ("each-approval-action", each_approval_action_fixtures),
    ("outbound-attempt", outbound_attempt_fixtures),
]


@pytest.mark.parametrize("scenario_name,builder", SCENARIOS)
def test_wp_rl_005_validators_pass_every_scenario(scenario_name, builder):
    fixtures = builder()
    results = run_wp_rl_005_validator_suite(fixtures)
    assert set(results) == set(WP_RL_005_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, (scenario_name, failures)


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_wp_rl_005_validators_reject_invalid_fixtures(name, fixture):
    validator = WP_RL_005_VALIDATORS[name]
    result = validator(fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_compose_drafts_yields_zero_or_one_per_opportunity_and_respects_budget():
    opps = [
        make_opportunity("o1"),
        make_opportunity("o2", source_url="https://reddit.com/r/SaaS/comments/def"),
        make_opportunity("o3", source_url="https://reddit.com/r/SaaS/comments/ghi"),
    ]
    drafts = compose_drafts(opps, provider_used="deepclaude", budget={"max_drafts_per_run": 2})
    assert len(drafts) == 2
    assert [d.opportunity_id for d in drafts] == ["o1", "o2"]
    for draft in drafts:
        assert draft.provider_used == "deepclaude"
        assert draft.target_url.startswith("https://")
        assert draft.state == "pending"
    assert compose_drafts([], provider_used="deepclaude") == []


def test_evaluate_slop_flags_only_slop_tells():
    clean = evaluate_slop(CLEAN_BODY)
    assert clean["flagged"] is False
    assert clean["warning"] is None
    slop = evaluate_slop(SLOP_BODY)
    assert slop["flagged"] is True
    assert slop["warning"]


def test_apply_approval_action_produces_attributable_state_results():
    approve = apply_approval_action(make_draft("d1", "o1"), "approve")
    assert approve.state == "approved"
    edit = apply_approval_action(make_draft("d1", "o1"), "edit_approve", new_body="edited")
    assert edit.state == "edited" and edit.body == "edited"
    regen = apply_approval_action(
        make_draft("d1", "o1"), "regenerate", new_body="fresh", new_draft_id="d2"
    )
    assert regen.state == "pending" and regen.draft_id == "d2" and regen.body == "fresh"
    skip = apply_approval_action(make_draft("d1", "o1"), "skip")
    assert skip.state == "rejected"


def test_draft_review_context_presents_five_classes_together():
    opp = make_opportunity("o1")
    draft = make_draft("d1", "o1", body=CLEAN_BODY)
    context = draft_review_context(draft, opp)
    assert context["source"] == opp.source_url
    assert context["body"] == CLEAN_BODY
    assert context["channel"] == "reddit"
    assert context["target"] == draft.target_url
    assert context["qualification_reason"] == opp.qualify_reason
