# TASK_336 — RDD: Selector-mode deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for selector-mode wiring so explicit-mode invocation, compatibility behavior, and fail-closed semantics remain regression-safe.

## Acceptance criteria
- Dedicated test script validates selector-mode matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - explicit selector mode enabled via invocation path yields expected triage output for bounded v1 case.
  - compatibility mode path remains valid for bounded legacy fixture shape.
- Required negative cases:
  - explicit mode with missing selector-map fails closed with stable reason marker.
  - explicit mode with invalid selector-map schema fails closed with stable reason marker.
- Existing triage selector tests remain passing.
- Determinism check runs selector-mode matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_selector_mode.sh` (new)
- `tests/fixtures/rdd_phase9_selector_mode_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_336/**`

## Files forbidden to touch
- `docs/dev/ASSIGNMENTS.md`
- `docs/dev/WORK_QUEUE.md`
- `docs/RESIDUAL_DISCRETION_DOCTRINE.md`
- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- `capabilities/capability-registry.json`
- `mcp/server.py`
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- `system/scripts/codex-unattended.sh`
- `scripts/policy-eval.py`
- `scripts/verify-chain.py`
- `scripts/replay-record.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_336/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_336/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_336/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_MODE__v1/TASK_336/HOTFILE_SCAN.txt`

## Determinism expectations
- Selector-mode test harness output hash is stable across repeated runs with identical fixtures.
- Selector-mode fail-closed markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
