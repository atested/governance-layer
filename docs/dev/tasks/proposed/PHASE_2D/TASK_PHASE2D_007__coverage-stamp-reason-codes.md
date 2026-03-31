# TASK_PHASE2D_007 — Coverage Stamp Reason Codes

## Scope
Define canonical reason-code taxonomy for coverage stamp validation outcomes across policy-eval, verify-chain, and replay contracts.

Required reason codes:
- `COVERAGE_STAMP_OK`
- `COVERAGE_STAMP_MISSING`
- `COVERAGE_STAMP_MALFORMED`
- `COVERAGE_STAMP_SURFACE_UNKNOWN`
- `COVERAGE_STAMP_PARTIAL`
- `COVERAGE_STAMP_ORDER_INVALID`

Reason code contract:
- Emit exactly one terminal reason code for each validation decision.
- Missing or malformed required coverage stamp is fail-closed.

Examples:
- PASS: `COVERAGE_STAMP_OK` when `coverage_stamp_v1` is present, ordered canonically, and complete.
- FAIL-CLOSED: `COVERAGE_STAMP_MISSING` with nonzero exit when required stamp is absent.

## Non-goals
- No implementation of reason-code emitters.
- No changes to existing non-coverage reason-code domains.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_007__coverage-stamp-reason-codes.md`

## Acceptance criteria
- Required reason-code set is explicit.
- Mapping rules for PASS vs FAIL-CLOSED are explicit.
- Includes PASS and FAIL-CLOSED examples.

## STOP conditions
- Stop if reason-code semantics conflict with existing fail-closed policy.
- Stop if taxonomy cannot be deterministic per input.

## Determinism notes
- Reason codes must be stable for identical inputs.
- Canonical reason code symbols are uppercase snake case and immutable within v1.
- Excluded: localized human-readable phrasing.
