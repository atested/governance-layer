"""WP-RL-007 conformance: complete validator catalog reconciliation.

The complete catalog must contain exactly the 43 source validators plus
ValidatorCatalogCompletenessValidator, and every validator must return
"passed": true against its conforming reconciliation fixture.
"""

import pytest

from reach_lite.reconciliation import build_conforming_fixtures, run_reconciliation
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
    run_complete_catalog,
    validator_catalog_completeness_validator,
)


def test_catalog_contains_exactly_43_source_validators():
    assert len(EXPECTED_VALIDATOR_NAMES) == 43
    assert len(set(EXPECTED_VALIDATOR_NAMES)) == 43
    assert set(VALIDATOR_CATALOG) == set(EXPECTED_VALIDATOR_NAMES)


def test_complete_catalog_adds_completeness_validator():
    assert len(COMPLETE_VALIDATOR_CATALOG) == 44
    assert "ValidatorCatalogCompletenessValidator" in COMPLETE_VALIDATOR_CATALOG
    assert set(VALIDATOR_CATALOG) <= set(COMPLETE_VALIDATOR_CATALOG)


def test_catalog_completeness_validator_passes_complete_catalog():
    result = validator_catalog_completeness_validator({"catalog": VALIDATOR_CATALOG})
    assert result["passed"] is True, result["findings"]


def test_catalog_completeness_validator_rejects_incomplete_catalog():
    incomplete = dict(VALIDATOR_CATALOG)
    incomplete.pop("AgentAtomValidator")
    result = validator_catalog_completeness_validator({"catalog": incomplete})
    assert result["passed"] is False
    assert any("AgentAtomValidator" in f for f in result["findings"])


def test_every_source_validator_passes_conforming_fixture():
    fixtures = build_conforming_fixtures()
    assert set(fixtures) == set(EXPECTED_VALIDATOR_NAMES)
    results = run_complete_catalog(fixtures)
    failures = {name: r["findings"] for name, r in results.items() if not r["passed"]}
    assert not failures, failures


def test_reconciliation_reports_all_passed():
    report = run_reconciliation()
    assert report["passed_all"] is True
    assert report["catalog_size"] == 43
    assert report["complete_catalog_size"] == 44
