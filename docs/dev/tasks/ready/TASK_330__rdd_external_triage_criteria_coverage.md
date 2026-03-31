# TASK_330 — RDD: External triage criteria deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded coverage for triage criteria-file behavior so criteria loading, fail-closed validation, and deterministic output are regression-safe.

## Acceptance criteria
- Dedicated test script validates criteria-file matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - valid criteria file yields expected triage output for bounded v1 case.
- Required negative cases:
  - missing criteria file fails closed with stable reason marker
  - malformed criteria file fails closed with stable reason marker
  - criteria file missing required fields fails closed with stable reason marker
- Existing triage tests remain passing.
- Determinism check runs matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_criteria_file.sh` (new)
- `tests/fixtures/rdd_phase6_triage_criteria_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_330/**`

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
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_330/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_330/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_330/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_CRITERIA_FILE__v1/TASK_330/HOTFILE_SCAN.txt`

## Determinism expectations
- Test harness output hash is stable across repeated runs with identical inputs.
- Fail-closed reasons are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded criteria-file seam for current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
