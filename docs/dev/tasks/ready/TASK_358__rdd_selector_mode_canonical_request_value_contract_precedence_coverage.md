# TASK_358 — RDD: Selector-mode canonical request value-contract precedence coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded deterministic coverage for canonical request selector-mode value-contract precedence so invalid canonical request mode values are classified as canonical-invalid before any legacy-source conflict path, while valid canonical conflict paths remain regression-safe.

## Acceptance criteria
- Dedicated coverage validates selector-mode source matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - canonical-only selector mode succeeds deterministically for allowed values.
  - canonical-only selector mode succeeds when request mode uses mixed-case/trimmed variants that normalize to allowed values.
  - canonical absent + no aliases keeps bounded default compatibility behavior.
- Required negative cases:
  - canonical request mode value outside allowed set after normalization fails closed with stable invalid marker.
  - canonical request mode non-string/empty values fail closed with stable invalid marker.
  - canonical request invalid value plus one or more legacy aliases fails closed with canonical invalid marker (not source-conflict marker).
  - canonical valid value plus legacy aliases continues to fail closed with existing source-conflict marker.
  - canonical absent + only `intent.rdd.selector_mode` fails closed with stable marker.
  - canonical absent + only `intent.selector_mode` fails closed with stable marker.
  - canonical absent + both legacy aliases where one or both values are non-string/empty fails closed with existing value-invalid marker.
  - canonical absent + both legacy aliases where one or both values are unsupported non-empty strings fails closed with existing value-unsupported marker.
- Existing selector-mode strictness and triage selector tests remain passing.
- Determinism check runs selector-mode source matrix twice and verifies stable normalized output hashes.
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.

## Files allowed to touch
- `tests/test_rdd_triage_selector_mode.sh`
- `tests/test_rdd_triage_eval.sh` (only if minimally required for bounded compatibility)
- `tests/test_rdd_triage_criteria_selector.sh` (only if minimally required for bounded compatibility)
- `tests/fixtures/rdd_phase20_selector_mode_*.json` (new or updated bounded fixtures)
- `scripts/rdd-pass-triage.sh`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_358/**`

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
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_358/TESTS.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_358/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_358/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PHASE20_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1/TASK_358/HOTFILE_SCAN.txt`

## Determinism expectations
- Selector-mode source matrix output hash is stable across repeated runs with identical fixtures.
- Legacy dual-alias invalid/unsupported/conflict/mismatch markers are deterministic and explicitly asserted.

## STOP rules
- STOP if coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced in bounded scope.

## Constraints
- Coverage stays within bounded selector-mode canonical request value-contract precedence seam for the current v1 case class.
- No server wiring and no doctrine changes.
- No merge work.
