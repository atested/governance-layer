"""WP-RL-004 conformance: Reddit discovery and brief-driven qualification.

The eight validators (RedditSourceBoundaryValidator, CandidateDeduplicationValidator,
BriefQualificationValidator, SeedKnowledgeBoundaryValidator, RunBudgetValidator,
OptionalPersonResolutionValidator, OpportunitySchemaValidator, PersonSchemaValidator)
must return "passed": true against authorized/unauthorized, repeated/later-interaction,
included/excluded, known/unknown-Person, and excess-candidate fixtures, and must reject
fixtures that leak the source boundary, over-collapse, invent qualification meaning,
require runtime corpus authoring, overrun a budget, or fabricate a Person link.
"""

import pytest

from reach_lite.domain import (
    Agent,
    Opportunity,
    Person,
    Run,
    default_budget,
    default_schedule,
    deduplicate_candidates,
    qualify_candidate,
    qualify_candidates,
    retrieve_authorized_candidates,
)
from reach_lite.validators import (
    WP_RL_004_VALIDATORS,
    run_wp_rl_004_validator_suite,
)


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_agent(agent_id="a1", state="live", sources=None, qualifier=None, **kw):
    base = dict(
        agent_id=agent_id,
        brief_text="Reach out to r/SaaS founders asking for feedback.",
        schedule=default_schedule(),
        sources=sources if sources is not None else [{"kind": "subreddit", "value": "r/SaaS"}],
        qualifier=qualifier if qualifier is not None else {"include": "feedback", "exclude": "hiring"},
        action="draft_reply",
        mode="ask",
        budget=default_budget(),
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
        source_url="https://reddit.com/r/SaaS/comments/abc",
        author_handle="alice",
        excerpt="Founders asking for feedback on pricing.",
        qualify_score=0.75,
        qualify_reason="matches inclusion intent: feedback",
        person_id="p1",
    )
    base.update(kw)
    return Opportunity(**base)


def make_person(person_id="p1", handles=None, **kw):
    base = dict(
        person_id=person_id,
        handles=handles if handles is not None else [{"kind": "reddit", "value": "alice"}],
        first_seen="2026-08-01T00:00:00",
        interactions=[{"kind": "reply", "url": "https://reddit.com/r/SaaS/comments/abc"}],
        notes="",
    )
    base.update(kw)
    return Person(**base)


def make_candidate(candidate_id="c1", **kw):
    base = dict(
        candidate_id=candidate_id,
        source={"kind": "subreddit", "value": "r/SaaS"},
        url="https://reddit.com/r/SaaS/comments/abc",
        author_handle="alice",
        excerpt="Founders asking for feedback on pricing.",
    )
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Base conforming fixture suite (all eight validators pass).
# ---------------------------------------------------------------------------

def success_fixtures():
    agent = make_agent("a1", "live")
    run = make_run("r1")
    person = make_person("p1")
    opp_known = make_opportunity("o1", run_id="r1", author_handle="alice", person_id="p1")
    opp_unknown = make_opportunity(
        "o2",
        run_id="r1",
        source_url="https://reddit.com/r/SaaS/comments/def",
        author_handle="ghost",
        person_id=None,
    )
    return {
        "RedditSourceBoundaryValidator": {
            "agent": agent,
            "candidates": [
                make_candidate("c-authorized", url="https://reddit.com/r/SaaS/comments/1"),
                make_candidate(
                    "c-unauthorized",
                    source={"kind": "subreddit", "value": "r/Other"},
                    url="https://reddit.com/r/Other/comments/2",
                ),
            ],
        },
        "CandidateDeduplicationValidator": {
            "agent_id": "a1",
            "opportunities": [opp_known, opp_unknown],
        },
        "BriefQualificationValidator": {
            "qualifier": {"include": "feedback", "exclude": "hiring"},
            "candidates": [
                make_candidate(
                    "c-include",
                    url="https://reddit.com/r/SaaS/comments/1",
                    excerpt="Founders asking for feedback on pricing",
                ),
                make_candidate(
                    "c-exclude",
                    url="https://reddit.com/r/SaaS/comments/4",
                    excerpt="We are hiring engineers now",
                ),
            ],
            "opportunities": [
                make_opportunity(
                    "o1",
                    source_url="https://reddit.com/r/SaaS/comments/1",
                    qualify_score=1.0,
                    qualify_reason="matches inclusion intent: feedback",
                ),
            ],
        },
        "SeedKnowledgeBoundaryValidator": {
            "seed_corpus_version": "v1.0.0",
            "qualification_evidence": [
                {"evidence_id": "e1", "seed_corpus_version": "v1.0.0"},
            ],
            "requires_corpus_edit": [],
        },
        "RunBudgetValidator": {
            "runs": [
                {
                    "run": make_run("r1", candidates_qualified=4, drafts_produced=3),
                    "budget": default_budget(),
                }
            ],
        },
        "OptionalPersonResolutionValidator": {
            "persons": [person],
            "opportunities": [opp_known, opp_unknown],
        },
        "OpportunitySchemaValidator": {
            "opportunities": [opp_known, opp_unknown],
            "runs": [run],
            "persons": [person],
        },
        "PersonSchemaValidator": {
            "persons": [person],
        },
    }


# ---------------------------------------------------------------------------
# Scenario suites: each must also yield passed: true for every validator.
# ---------------------------------------------------------------------------

def authorized_unauthorized_fixtures():
    fixtures = success_fixtures()
    fixtures["RedditSourceBoundaryValidator"] = {
        "agent": make_agent("a1", "live"),
        "candidates": [
            make_candidate("c-authorized", url="https://reddit.com/r/SaaS/comments/1"),
            make_candidate(
                "c-unauthorized",
                source={"kind": "subreddit", "value": "r/Other"},
                url="https://reddit.com/r/Other/comments/2",
            ),
            make_candidate(
                "c-fake",
                source={"kind": "subreddit", "value": "r/Fake"},
                url="https://reddit.com/r/Fake/comments/3",
            ),
        ],
    }
    return fixtures


def repeated_later_interaction_fixtures():
    fixtures = success_fixtures()
    fixtures["CandidateDeduplicationValidator"] = {
        "agent_id": "a1",
        "opportunities": [
            make_opportunity("o1", source_url="https://reddit.com/r/SaaS/comments/post"),
            make_opportunity(
                "o2",
                source_url="https://reddit.com/r/SaaS/comments/post/comment/1",
                author_handle="bob",
                person_id=None,
            ),
        ],
    }
    return fixtures


def included_excluded_fixtures():
    fixtures = success_fixtures()
    fixtures["BriefQualificationValidator"] = {
        "qualifier": {"include": "feedback pricing", "exclude": "hiring partnership"},
        "candidates": [
            make_candidate(
                "c-include-1",
                url="https://reddit.com/r/SaaS/comments/1",
                excerpt="Founders asking for feedback on pricing",
            ),
            make_candidate(
                "c-include-2",
                url="https://reddit.com/r/SaaS/comments/2",
                excerpt="Feedback request about pricing tiers",
            ),
            make_candidate(
                "c-exclude-1",
                url="https://reddit.com/r/SaaS/comments/3",
                excerpt="We are hiring engineers now",
            ),
            make_candidate(
                "c-exclude-2",
                url="https://reddit.com/r/SaaS/comments/4",
                excerpt="Looking for a partnership",
            ),
        ],
        "opportunities": [
            make_opportunity(
                "o1",
                source_url="https://reddit.com/r/SaaS/comments/1",
                qualify_score=1.0,
                qualify_reason="matches inclusion intent: feedback pricing",
            ),
            make_opportunity(
                "o2",
                source_url="https://reddit.com/r/SaaS/comments/2",
                qualify_score=1.0,
                qualify_reason="matches inclusion intent: feedback pricing",
            ),
        ],
    }
    return fixtures


def known_unknown_person_fixtures():
    fixtures = success_fixtures()
    person = make_person("p1", handles=[{"kind": "reddit", "value": "alice"}])
    opp_known = make_opportunity("o1", author_handle="alice", person_id="p1")
    opp_unknown = make_opportunity(
        "o2", author_handle="ghost", person_id=None,
        source_url="https://reddit.com/r/SaaS/comments/def",
    )
    fixtures["OptionalPersonResolutionValidator"] = {
        "persons": [person],
        "opportunities": [opp_known, opp_unknown],
    }
    fixtures["OpportunitySchemaValidator"] = {
        "opportunities": [opp_known, opp_unknown],
        "runs": [make_run("r1")],
        "persons": [person],
    }
    return fixtures


def excess_candidate_fixtures():
    fixtures = success_fixtures()
    fixtures["RunBudgetValidator"] = {
        "runs": [
            {
                "run": make_run(
                    "r1", candidates_seen=50, candidates_qualified=5, drafts_produced=3
                ),
                "budget": default_budget(),
            }
        ],
    }
    return fixtures


# ---------------------------------------------------------------------------
# Invalid cases: each must yield passed: false.
# ---------------------------------------------------------------------------

INVALID_CASES = [
    (
        "RedditSourceBoundaryValidator",
        {
            "agent": make_agent("a1", "live"),
            "candidates": [
                make_candidate("c-authorized", url="https://reddit.com/r/SaaS/comments/1"),
                make_candidate(
                    "c-unauthorized",
                    source={"kind": "subreddit", "value": "r/Other"},
                    url="https://reddit.com/r/Other/comments/2",
                ),
            ],
            "retrieved": [
                make_candidate("c-authorized", url="https://reddit.com/r/SaaS/comments/1"),
                make_candidate(
                    "c-unauthorized",
                    source={"kind": "subreddit", "value": "r/Other"},
                    url="https://reddit.com/r/Other/comments/2",
                ),
            ],
        },
    ),
    (
        "CandidateDeduplicationValidator",
        {
            "agent_id": "a1",
            "opportunities": [
                make_opportunity("o1", source_url="https://reddit.com/r/SaaS/comments/post"),
                make_opportunity("o2", source_url="https://reddit.com/r/SaaS/comments/post"),
            ],
        },
    ),
    (
        "BriefQualificationValidator",
        {
            "qualifier": {"include": "feedback", "exclude": "hiring"},
            "candidates": [
                make_candidate(
                    "c-exclude",
                    url="https://reddit.com/r/SaaS/comments/4",
                    excerpt="We are hiring engineers now",
                ),
            ],
            "opportunities": [
                make_opportunity(
                    "o1",
                    source_url="https://reddit.com/r/SaaS/comments/4",
                    qualify_score=0.9,
                    qualify_reason="invented meaning",
                ),
            ],
        },
    ),
    (
        "SeedKnowledgeBoundaryValidator",
        {
            "seed_corpus_version": "v1.0.0",
            "qualification_evidence": [
                {"evidence_id": "e1", "seed_corpus_version": "v1.0.0"},
            ],
            "requires_corpus_edit": ["operator must add new seed patterns each run"],
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
        "OptionalPersonResolutionValidator",
        {
            "persons": [make_person("p1")],
            "opportunities": [
                make_opportunity("o1", author_handle="ghost", person_id="p1"),
            ],
        },
    ),
    (
        "OpportunitySchemaValidator",
        {
            "opportunities": [
                make_opportunity("o1", qualify_score=1.5),
            ],
            "runs": [make_run("r1")],
            "persons": [make_person("p1")],
        },
    ),
    (
        "PersonSchemaValidator",
        {
            "persons": [
                make_person("p1"),
                make_person("p1", handles=[{"kind": "reddit", "value": "bob"}]),
            ],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("authorized-unauthorized", authorized_unauthorized_fixtures),
    ("repeated-later-interaction", repeated_later_interaction_fixtures),
    ("included-excluded", included_excluded_fixtures),
    ("known-unknown-person", known_unknown_person_fixtures),
    ("excess-candidate", excess_candidate_fixtures),
]


@pytest.mark.parametrize("scenario_name,builder", SCENARIOS)
def test_wp_rl_004_validators_pass_every_scenario(scenario_name, builder):
    fixtures = builder()
    results = run_wp_rl_004_validator_suite(fixtures)
    assert set(results) == set(WP_RL_004_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, (scenario_name, failures)


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_wp_rl_004_validators_reject_invalid_fixtures(name, fixture):
    validator = WP_RL_004_VALIDATORS[name]
    result = validator(fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_retrieve_authorized_candidates_respects_source_boundary():
    agent = make_agent("a1", "live")
    candidates = [
        make_candidate("c1", url="https://reddit.com/r/SaaS/comments/1"),
        make_candidate(
            "c2",
            source={"kind": "subreddit", "value": "r/Other"},
            url="https://reddit.com/r/Other/comments/2",
        ),
    ]
    retrieved = retrieve_authorized_candidates(agent, candidates)
    assert [c["candidate_id"] for c in retrieved] == ["c1"]
    assert retrieved[0]["source"]["value"] == "r/SaaS"
    assert retrieved[0]["url"].startswith("https://")


def test_deduplicate_candidates_collapses_repeats_but_keeps_distinct_later_interaction():
    candidates = [
        make_candidate("c1", url="https://reddit.com/r/SaaS/comments/post"),
        make_candidate("c2", url="https://reddit.com/r/SaaS/comments/post"),
        make_candidate("c3", url="https://reddit.com/r/SaaS/comments/post/comment/1"),
    ]
    deduped = deduplicate_candidates(candidates)
    assert [c["candidate_id"] for c in deduped] == ["c1", "c3"]


def test_qualify_candidate_applies_inclusion_and_exclusion_intent():
    qualifier = {"include": "feedback", "exclude": "hiring"}
    included = qualify_candidate(
        make_candidate(excerpt="Founders asking for feedback"), qualifier
    )
    assert included["verdict"] == "included"
    assert included["score"] > 0
    assert included["reason"]
    excluded = qualify_candidate(
        make_candidate(excerpt="We are hiring engineers"), qualifier
    )
    assert excluded["verdict"] == "excluded"
    assert excluded["score"] == 0.0
    no_signal = qualify_candidate(make_candidate(excerpt="random chatter"), qualifier)
    assert no_signal["verdict"] == "excluded"


def test_qualify_candidates_returns_only_included():
    qualifier = {"include": "feedback", "exclude": "hiring"}
    candidates = [
        make_candidate("c1", excerpt="feedback please"),
        make_candidate("c2", excerpt="hiring now"),
    ]
    qualified = qualify_candidates(candidates, qualifier)
    assert [c["candidate_id"] for c in qualified] == ["c1"]
