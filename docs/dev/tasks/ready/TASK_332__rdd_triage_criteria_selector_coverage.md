# TASK_332 — RDD: Triage criteria selector deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded coverage for criteria-selector behavior so selector derivation, fail-closed handling, and deterministic output remain regression-safe as the external criteria seam evolves.

## Acceptance criteria
- Dedicated test script validates selector matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - supported Pass `insufficiency` selector yields expected triage output for the bounded v1 case class.
- Required negative cases:
  - unsupported insufficiency selector fails closed with stable reason marker
  - missing selector-mapped criteria entry fails closed with stable reason marker
  - malformed selector fixture input fails closed with stable reason marker
- Existing triage tests remain passing.
- Determinism check runs selector matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_criteria_selector.sh` (new)
- `tests/fixtures/rdd_phase7_triage_criteria_selector_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_332/**`

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
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_332/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_332/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_332/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_SELECTOR__v1/TASK_332/HOTFILE_SCAN.txt`

## Determinism expectations
- Test harness output hash is stable across repeated runs with identical selector fixtures.
- Fail-closed selector reason markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
