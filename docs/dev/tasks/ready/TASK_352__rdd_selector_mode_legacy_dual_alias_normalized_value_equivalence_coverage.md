# TASK_352 — RDD: Selector-mode legacy dual-alias normalized-value equivalence coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for legacy dual-alias normalized-value equivalence handling so whitespace-only formatting differences in allowed values are classified correctly while existing invalid/unsupported paths remain regression-safe.

## Acceptance criteria
- Dedicated coverage validates selector-mode source matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - canonical-only selector mode succeeds deterministically.
  - canonical absent + no aliases keeps bounded default compatibility behavior.
- Required negative cases:
  - canonical absent + only `intent.rdd.selector_mode` fails closed with stable marker.
  - canonical absent + only `intent.selector_mode` fails closed with stable marker.
  - canonical absent + both legacy aliases with equal normalized allowed values fails closed with existing conflict marker.
  - canonical absent + both legacy aliases with different normalized allowed values fails closed with existing mismatch marker.
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
- `tests/fixtures/rdd_phase17_selector_mode_*.json` (new or updated bounded fixtures)
- `scripts/rdd-pass-triage.sh`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_352/**`

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
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_352/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_352/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_352/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE17_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1/TASK_352/HOTFILE_SCAN.txt`

## Determinism expectations
- Selector-mode source matrix output hash is stable across repeated runs with identical fixtures.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode legacy dual-alias normalized-value seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
