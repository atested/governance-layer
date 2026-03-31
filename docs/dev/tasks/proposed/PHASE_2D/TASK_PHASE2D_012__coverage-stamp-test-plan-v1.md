# TASK_PHASE2D_012 — Coverage Stamp Test Plan v1

## Scope
Define v1 test-plan contract for coverage stamp validation across policy-eval, verify-chain, and replay.

Planned test set:
- `tests/test_coverage_stamp_policy_eval.sh`
- `tests/test_coverage_stamp_verify_chain.sh`
- `tests/test_coverage_stamp_replay.sh`
- `tests/test_coverage_stamp_ordering_determinism.sh`

Required assertions:
- deterministic output digest equality across two runs
- fail-closed on required missing/malformed stamps
- deterministic SKIP only when optional semantics are explicitly declared

Examples:
- PASS: deterministic ordering test yields identical digest run1/run2 and rc=0.
- FAIL-CLOSED: missing required stamp test yields rc!=0 with stable reason code.

## Non-goals
- No implementation of tests in this task.
- No modification of runtime scripts.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_012__coverage-stamp-test-plan-v1.md`

## Acceptance criteria
- Test names are explicit and implementation-ready.
- Expected rc behavior is explicit per class of test.
- PASS + FAIL-CLOSED examples included.

## STOP conditions
- Stop if any test case lacks deterministic expected rc behavior.
- Stop if SKIP is used without explicit optional contract basis.

## Determinism notes
- Test outputs must compare normalized canonical artifacts and stable stdout sections.
- Excluded: ephemeral timestamps and temporary directory prefixes unless normalized.
