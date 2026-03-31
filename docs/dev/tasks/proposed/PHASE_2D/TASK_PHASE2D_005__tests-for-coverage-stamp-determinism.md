# TASK_PHASE2D_005 — Tests for Coverage Stamp Determinism

## Scope
Define executable-grade test set (names, fixtures, rc expectations) for coverage stamp determinism and fail-closed behavior.

Planned tests:
- `tests/test_coverage_stamp_determinism.sh`
  - Fixture: `tests/fixtures/coverage_stamp/complete_v1.json`
  - Expected rc: 0
  - Assertion: identical digest across two runs.
- `tests/test_coverage_stamp_missing_required.sh`
  - Fixture: `tests/fixtures/coverage_stamp/missing_required.json`
  - Expected rc: 1
  - Assertion: fail-closed with stable reason code.
- `tests/test_coverage_stamp_partial_required.sh`
  - Fixture: `tests/fixtures/coverage_stamp/partial_required.json`
  - Expected rc: 1
  - Assertion: deterministic partial-coverage failure output.
- `tests/test_coverage_stamp_optional_skip.sh`
  - Fixture: `tests/fixtures/coverage_stamp/optional_absent.json`
  - Expected rc: 3 (only when spec marks optional path as SKIP)
  - Assertion: deterministic SKIP marker.

## Non-goals
- No implementation of test scripts in this restock task.
- No modifications to release-gate/test harness code.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_005__tests-for-coverage-stamp-determinism.md`

## Acceptance criteria
- Test list includes concrete script paths.
- Fixture paths are explicit.
- Expected rc behavior is explicit per test.
- Determinism/fail-closed/SKIP semantics are explicit.

## STOP conditions
- Stop if any test cannot define deterministic rc behavior.
- Stop if SKIP semantics are used without explicit optional-spec basis.

## Determinism notes
- Each test must compare run1/run2 digests for primary output.
- Excluded: machine-specific temporary directory prefixes unless normalized.
