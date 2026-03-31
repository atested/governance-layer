# TASK_322 — RDD: Triage evaluator test coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded regression and negative-control coverage for the new Phase 2 triage evaluator and Pass→Triage invocation flow for the FS_COPY dest-exists-no-overwrite case class.

## Acceptance criteria
- New dedicated test script covers:
  - UNDECIDED Pass input triggers triage invocation.
  - Triage output contains required fields: findings, governing condition, disposition, structural signals.
  - `originating_pass_hash`, `process_id`, and `prev_record_hash` linkage are correct.
  - Non-UNDECIDED Pass input skips triage invocation.
  - Malformed/non-UNDECIDED Pass input to triage-eval fails closed.
- Test output uses explicit PASS/FAIL case markers and non-zero exit on any failure.
- Determinism check runs triage path twice with identical normalized outputs.
- Existing Phase 1 UNDECIDED coverage still passes (`tests/test_policy_pass_undecided.sh`).
- Existing signing adjacency gates still pass:
  - `tests/test_signing_emit.sh`
  - `tests/test_signing_determinism.sh`

## Files allowed to touch
- `tests/test_rdd_triage_eval.sh` (new)
- `tests/fixtures/rdd_triage_pass_undecided_input.json` (new or updated)
- `tests/fixtures/rdd_triage_pass_allow_input.json` (new or updated)
- `scripts/rdd-pass-triage.sh`
- `scripts/triage-eval.py`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_322/**`

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
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_322/TESTS.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_322/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_322/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/TASK_322/HOTFILE_SCAN.txt`

## Determinism expectations
- Test script demonstrates two-run deterministic match for triage-path normalized outputs and records matching hashes.

## STOP rules
- STOP if adequate coverage requires editing protected hot files.
- STOP if triage testability requires doctrine/process/planning changes.
- STOP if forbidden files must be edited.

## Constraints
- Coverage is bounded to Phase 2 triage evaluator and invocation seam.
- No Phase 3 chain-verifier expansion.
- No Phase 4 signal-extractor implementation.
- No merge work.
