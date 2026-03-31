# TASK_338 — RDD: Selector-mode source-contract deterministic coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for selector-mode source contract behavior so precedence, fail-closed semantics, and backward-compatible defaults remain regression-safe.

## Acceptance criteria
- Dedicated coverage validates selector-mode source contract matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - request-bound selector mode is applied deterministically.
  - absent request-bound selector mode preserves bounded compatibility behavior.
- Required negative cases:
  - invalid request-bound selector mode fails closed with stable reason marker.
  - explicit mode selector-map contract failures remain fail-closed with stable reason markers.
- Existing selector-mode and triage selector tests remain passing.
- Determinism check runs source-contract matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase10_selector_mode_*.json` (new or updated bounded fixtures)
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_338/**`

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
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_338/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_338/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_338/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE10_SELECTOR_MODE_SOURCE__v1/TASK_338/HOTFILE_SCAN.txt`

## Determinism expectations
- Source-contract harness output hash is stable across repeated runs with identical fixtures.
- Fail-closed source-contract markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode source-contract seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
