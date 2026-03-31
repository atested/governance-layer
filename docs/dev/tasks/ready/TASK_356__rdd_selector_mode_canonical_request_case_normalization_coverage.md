# TASK_356 — RDD: Selector-mode canonical request case-normalization coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for canonical request selector-mode case-normalization handling so case-only formatting differences in canonical request mode values are classified correctly while existing legacy dual-alias fail-closed paths remain regression-safe.

## Acceptance criteria
- Dedicated coverage validates selector-mode source matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - canonical-only selector mode succeeds deterministically for normalized lowercase allowed values.
  - canonical-only selector mode succeeds when request mode uses mixed-case/trimmed variants that normalize to allowed values.
  - canonical absent + no aliases keeps bounded default compatibility behavior.
- Required negative cases:
  - canonical request mode value outside allowed set after normalization fails closed with stable invalid marker.
  - canonical absent + only `intent.rdd.selector_mode` fails closed with stable marker.
  - canonical absent + only `intent.selector_mode` fails closed with stable marker.
  - canonical absent + both legacy aliases where one or both values are non-string/empty fails closed with existing value-invalid marker.
  - canonical absent + both legacy aliases where one or both values are unsupported non-empty strings fails closed with existing value-unsupported marker.
  - canonical conflict cases from prior phases remain passing.
- Existing selector-mode strictness and triage selector tests remain passing.
- Determinism check runs selector-mode source matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase19_selector_mode_*.json` (new or updated bounded fixtures)
- `scripts/rdd-pass-triage.sh`
- `docs/dev/evidence/RDD_PHASE19_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1/TASK_356/**`

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
- `docs/dev/evidence/RDD_PHASE19_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1/TASK_356/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE19_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1/TASK_356/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE19_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1/TASK_356/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE19_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1/TASK_356/HOTFILE_SCAN.txt`

## Determinism expectations
- Selector-mode source matrix output hash is stable across repeated runs with identical fixtures.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode canonical request case-normalization seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
