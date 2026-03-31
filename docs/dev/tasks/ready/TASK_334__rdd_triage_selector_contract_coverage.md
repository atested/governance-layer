# TASK_334 — RDD: Triage selector contract deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for selector-contract strictness so contract-validation paths, fail-closed behavior, and selector-routing output remain regression-safe.

## Acceptance criteria
- Dedicated test script validates selector-contract matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - valid selector-map + target key yields expected triage output for the bounded v1 selector path.
- Required negative cases:
  - selector-map missing when explicit-map mode is required fails closed with stable reason marker
  - selector-map wrong-type/non-string entry fails closed with stable reason marker
  - selector target missing fails closed with stable reason marker
  - unsupported selector fails closed with stable reason marker
- Existing triage selector tests remain passing.
- Determinism check runs contract matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_criteria_selector.sh`
- `tests/fixtures/rdd_phase8_triage_selector_contract_*.json` (new or updated bounded fixtures)
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `scripts/triage-eval.py`
- `scripts/attest/rdd_triage_criteria.v1.json`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_334/**`

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
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_334/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_334/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_334/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_SELECTOR_CONTRACT__v1/TASK_334/HOTFILE_SCAN.txt`

## Determinism expectations
- Test harness output hash is stable across repeated runs with identical selector-contract fixtures.
- Fail-closed selector-contract reason markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-contract seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
