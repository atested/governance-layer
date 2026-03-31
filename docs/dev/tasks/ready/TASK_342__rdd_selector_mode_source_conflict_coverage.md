# TASK_342 — RDD: Selector-mode source-conflict coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for selector-mode source-conflict handling so conflicting multi-source declarations fail closed with stable markers and canonical-only behavior remains regression-safe.

## Acceptance criteria
- Dedicated coverage validates source-conflict matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - canonical-only selector mode succeeds deterministically.
  - canonical absent + no aliases keeps bounded default compatibility behavior.
- Required negative cases:
  - canonical + `intent.rdd.selector_mode` fails closed with stable marker.
  - canonical + `intent.selector_mode` fails closed with stable marker.
  - canonical + both legacy aliases fails closed with stable marker.
- Existing selector-mode strictness and triage selector tests remain passing.
- Determinism check runs source-conflict matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase12_selector_mode_*.json` (new or updated bounded fixtures)
- `scripts/rdd-pass-triage.sh`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_342/**`

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
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_342/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_342/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_342/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE12_SELECTOR_MODE_SOURCE_CONFLICT__v1/TASK_342/HOTFILE_SCAN.txt`

## Determinism expectations
- Source-conflict matrix output hash is stable across repeated runs with identical fixtures.
- Source-conflict fail-closed markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode source-conflict seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
