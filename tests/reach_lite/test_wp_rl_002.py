"""WP-RL-002 conformance: provider task boundary and activation evidence.

The six provider validators must return "passed": true against success,
unavailable, malformed-result, and insufficient-golden-set fixtures (truthful
behavior, no silent fallback), and must reject fixtures that leak a divergent
task shape or conceal an unavailable provider.
"""

import pytest

from reach_lite.domain import ProviderTaskInvocation
from reach_lite.validators import PROVIDER_VALIDATORS, run_provider_validator_suite


# ---------------------------------------------------------------------------
# Fixture factories.
# ---------------------------------------------------------------------------

def make_invocation(invocation_id="i1", **kw):
    base = dict(
        invocation_id=invocation_id,
        task_type="qualify",
        provider_requested="local",
        provider_used="local",
        input_ref="in1",
        result_ref="res1",
        started_at="2026-08-21T09:00:00",
        finished_at="2026-08-21T09:00:01",
        status="succeeded",
        failure_reason=None,
    )
    base.update(kw)
    return ProviderTaskInvocation(**base)


def _contracts():
    return {
        "chat": {"input_shape": ["messages"], "output_shape": ["reply"]},
        "qualify": {
            "input_shape": ["candidate", "brief"],
            "output_shape": ["verdict", "score", "reason"],
        },
        "compose": {
            "input_shape": ["opportunity", "voice"],
            "output_shape": ["draft"],
        },
    }


def _sufficient_golden_set():
    return {
        "candidate_verdicts": [
            {"id": "v%02d" % i, "expected": True, "actual": True, "match": True}
            for i in range(20)
        ],
        "voice_judged_drafts": [
            {"id": "d%02d" % i, "passes": True} for i in range(10)
        ],
    }


# ---------------------------------------------------------------------------
# Success fixture suite (all validators conforming).
# ---------------------------------------------------------------------------

def success_fixtures():
    return {
        "ProviderTaskContractValidator": {
            "task_contracts": _contracts(),
            "provider_contracts": [],
        },
        "ProviderChoiceValidator": {
            "providers": ["codex", "deepclaude", "local"],
            "availability": {"codex": True, "deepclaude": True, "local": True},
            "selections": [
                {"provider": "codex", "started": True, "reason": None, "invocation": "inv-codex-1"},
                {"provider": "local", "started": True, "reason": None, "invocation": "inv-local-1"},
            ],
        },
        "ProviderRoutingValidator": {
            "routing": {"chat": "codex", "qualify": "local", "compose": "local"},
            "dispatches": [
                {"task_type": "chat", "provider_requested": "codex", "provider_used": "codex", "evidence": {"provider": "codex"}},
                {"task_type": "qualify", "provider_requested": "local", "provider_used": "local", "evidence": {"provider": "local"}},
                {"task_type": "compose", "provider_requested": "local", "provider_used": "local", "evidence": {"provider": "local"}},
            ],
        },
        "ProviderFailureValidator": {"failures": []},
        "ProviderSwapGateValidator": {
            "golden_set": _sufficient_golden_set(),
            "activation": {"provider": "codex", "activated": True},
        },
        "ProviderInvocationSchemaValidator": {
            "invocations": [make_invocation()],
            "input_refs": ["in1"],
            "result_refs": ["res1"],
        },
    }


# ---------------------------------------------------------------------------
# Scenario suites: each must also yield passed: true for every validator.
# ---------------------------------------------------------------------------

def unavailable_fixtures():
    fixtures = success_fixtures()
    fixtures["ProviderChoiceValidator"] = {
        "providers": ["codex", "deepclaude", "local"],
        "availability": {"codex": False, "deepclaude": True, "local": True},
        "selections": [
            {"provider": "codex", "started": False, "reason": "missing_authentication", "invocation": None},
            {"provider": "local", "started": True, "reason": None, "invocation": "inv-local-1"},
        ],
    }
    fixtures["ProviderFailureValidator"] = {
        "failures": [
            {
                "provider_requested": "codex",
                "status": "failed",
                "failure_reason": "provider unavailable",
                "result_ref": None,
                "provider_used": None,
                "substituted_result": None,
            }
        ]
    }
    fixtures["ProviderInvocationSchemaValidator"] = {
        "invocations": [
            make_invocation(
                invocation_id="i-unavailable",
                task_type="chat",
                provider_requested="codex",
                provider_used=None,
                input_ref="in-chat",
                result_ref=None,
                finished_at="2026-08-21T09:00:01",
                status="failed",
                failure_reason="provider unavailable",
            )
        ],
        "input_refs": ["in-chat"],
        "result_refs": [],
    }
    return fixtures


def malformed_result_fixtures():
    fixtures = success_fixtures()
    fixtures["ProviderFailureValidator"] = {
        "failures": [
            {
                "provider_requested": "deepclaude",
                "status": "failed",
                "failure_reason": "malformed result",
                "result_ref": None,
                "provider_used": None,
                "substituted_result": None,
            }
        ]
    }
    fixtures["ProviderInvocationSchemaValidator"] = {
        "invocations": [
            make_invocation(
                invocation_id="i-malformed",
                task_type="compose",
                provider_requested="deepclaude",
                provider_used=None,
                input_ref="in-compose",
                result_ref=None,
                finished_at="2026-08-21T09:00:01",
                status="failed",
                failure_reason="malformed result",
            )
        ],
        "input_refs": ["in-compose"],
        "result_refs": [],
    }
    return fixtures


def insufficient_golden_set_fixtures():
    fixtures = success_fixtures()
    fixtures["ProviderSwapGateValidator"] = {
        "golden_set": {
            "candidate_verdicts": [
                {"id": "v%02d" % i, "expected": True, "actual": True, "match": True}
                for i in range(19)
            ],
            "voice_judged_drafts": [
                {"id": "d%02d" % i, "passes": True} for i in range(10)
            ],
        },
        "activation": {"provider": "codex", "activated": False},
    }
    return fixtures


# ---------------------------------------------------------------------------
# Invalid cases: each must yield passed: false (no silent fallback).
# ---------------------------------------------------------------------------

INVALID_CASES = [
    (
        "ProviderTaskContractValidator",
        {
            "task_contracts": {
                "chat": {"input_shape": ["messages"], "output_shape": ["reply"]},
                "qualify": {"input_shape": ["candidate"], "output_shape": ["verdict"]},
            },
            "provider_contracts": [{"provider": "codex", "task_type": "compose", "prompt": "..."}],
        },
    ),
    (
        "ProviderChoiceValidator",
        {
            "providers": ["codex", "deepclaude", "local"],
            "availability": {"codex": False, "deepclaude": True, "local": True},
            "selections": [
                {"provider": "codex", "started": True, "reason": None, "invocation": "inv-codex-1"},
            ],
        },
    ),
    (
        "ProviderRoutingValidator",
        {
            "routing": {"chat": "codex", "qualify": "local", "compose": "local"},
            "dispatches": [
                {"task_type": "chat", "provider_requested": "codex", "provider_used": "local", "evidence": {"provider": "local"}},
            ],
        },
    ),
    (
        "ProviderFailureValidator",
        {
            "failures": [
                {
                    "provider_requested": "codex",
                    "status": "failed",
                    "failure_reason": "provider unavailable",
                    "result_ref": None,
                    "provider_used": "local",
                    "substituted_result": None,
                }
            ]
        },
    ),
    (
        "ProviderSwapGateValidator",
        {
            "golden_set": {
                "candidate_verdicts": [
                    {"id": "v%02d" % i, "expected": True, "actual": True, "match": True}
                    for i in range(19)
                ],
                "voice_judged_drafts": [
                    {"id": "d%02d" % i, "passes": True} for i in range(10)
                ],
            },
            "activation": {"provider": "codex", "activated": True},
        },
    ),
    (
        "ProviderInvocationSchemaValidator",
        {
            "invocations": [
                make_invocation(
                    invocation_id="i-substituted",
                    task_type="qualify",
                    provider_requested="deepclaude",
                    provider_used="local",
                )
            ],
            "input_refs": ["in1"],
            "result_refs": ["res1"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("success", success_fixtures),
    ("unavailable", unavailable_fixtures),
    ("malformed_result", malformed_result_fixtures),
    ("insufficient_golden_set", insufficient_golden_set_fixtures),
]


@pytest.mark.parametrize("scenario_name,builder", SCENARIOS)
def test_all_provider_validators_pass_every_scenario(scenario_name, builder):
    fixtures = builder()
    results = run_provider_validator_suite(fixtures)
    assert set(results) == set(PROVIDER_VALIDATORS)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, (scenario_name, failures)


@pytest.mark.parametrize("name,fixture", INVALID_CASES)
def test_provider_validators_reject_silent_fallback(name, fixture):
    result = PROVIDER_VALIDATORS[name](fixture)
    assert result["passed"] is False, (name, result["findings"])


def test_provider_vocabularies_are_distinct_and_complete():
    from reach_lite.domain import INVOCATION_STATUSES, PROVIDERS, TASK_TYPES

    assert TASK_TYPES == ("chat", "qualify", "compose")
    assert PROVIDERS == ("codex", "deepclaude", "local")
    assert INVOCATION_STATUSES == ("running", "succeeded", "failed")
    assert len(set(PROVIDERS)) == 3
    assert len(set(TASK_TYPES)) == 3
