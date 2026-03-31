# TASK_328 — RDD: Replay extension deterministic test coverage

SPEC_EXPECTED: CODE

## Intent
Add bounded test coverage for Phase 5 replay-extension behavior so triage/terminal replay checks and failure modes are deterministic, auditable, and regression-safe.

## Acceptance criteria
- Dedicated test script validates Phase 5 replay matrix with explicit PASS/FAIL markers.
- Required positive cases:
  - triage record replay integrity path passes under valid fixture
  - terminal record replay integrity path passes under valid fixture
- Required negative cases:
  - malformed/missing required originating-link field fails closed with stable reason marker
  - unsupported record category fails closed with stable reason marker
- Existing pass replay tests remain passing (no regression).
- Test script exits non-zero on any failure and prints aggregate PASS/FAIL.
- Determinism check runs matrix twice and verifies stable normalized output hashes.

## Files allowed to touch
- `tests/test_replay_rdd_phase5.sh` (new)
- `tests/fixtures/rdd_phase5_replay_*.json` (new or updated bounded fixtures)
- `tests/test_replay.sh` (only if minimally required to include bounded Phase 5 regression invocation)
- `scripts/replay-record.py`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_328/**`

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
- `scripts/triage-eval.py`
- `scripts/verify-chain.py`
- Everything else.

## Required evidence artifacts
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_328/TESTS.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_328/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_328/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_REPLAY_EXTENSION__v1/TASK_328/HOTFILE_SCAN.txt`

## Determinism expectations
- Test harness emits stable normalized output hashes across repeated runs with identical fixtures.
- Expected-failure markers are deterministic.

## STOP rules
- STOP if adequate coverage requires hot-file edits.
- STOP if coverage requires doctrine/server/registry/process changes.
- STOP if deterministic assertions cannot be produced within this bounded seam.

## Constraints
- Coverage stays within Phase 5 replay-extension seam.
- No runtime terminal judgment implementation.
- No merge work.
