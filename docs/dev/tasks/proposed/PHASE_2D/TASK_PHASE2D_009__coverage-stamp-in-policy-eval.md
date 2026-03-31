# TASK_PHASE2D_009 — Coverage Stamp in policy-eval

## Scope
Specify policy-eval contract for reading, validating, and reporting coverage stamp fields.

Contract points:
- policy-eval reads `coverage_stamp_v1` from declared input metadata.
- policy-eval emits coverage validation status and reason code.
- Required profiles fail-closed on missing/malformed/partial coverage stamp.

Examples:
- PASS: required profile with complete canonical coverage stamp emits `COVERAGE_STAMP_OK` and rc=0.
- FAIL-CLOSED: required profile with malformed stamp emits `COVERAGE_STAMP_MALFORMED` and rc!=0.

## Non-goals
- No changes to non-coverage policy intent evaluation.
- No release-gate integration changes in this scoping task.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_009__coverage-stamp-in-policy-eval.md`

## Acceptance criteria
- policy-eval input and output coverage contract points are explicit.
- Required-profile fail-closed semantics are explicit.
- PASS + FAIL-CLOSED examples included.

## STOP conditions
- Stop if required-profile behavior would become informational-only.
- Stop if reason-code mapping is ambiguous.

## Determinism notes
- Same input stamp must produce same reason code and rc.
- Output ordering must follow canonical ordering rules from TASK_PHASE2D_008.
- Excluded: profiling/timing diagnostics.
