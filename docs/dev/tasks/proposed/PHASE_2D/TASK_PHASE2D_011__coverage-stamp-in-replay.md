# TASK_PHASE2D_011 — Coverage Stamp in replay

## Scope
Specify replay contract for preserving and reporting coverage stamp semantics during replay operations.

Contract points:
- replay reads coverage stamp from source records.
- replay output includes coverage summary with Observation/Enforcement/Provenance status.
- required replay mode fails closed when required stamp is absent or malformed.

Examples:
- PASS: replay emits deterministic coverage section with `coverage_stamp_v1` and rc=0.
- FAIL-CLOSED: replay detects malformed stamp and exits nonzero with stable reason code.

## Non-goals
- No modification of replay functional semantics outside coverage reporting.
- No changes to non-coverage replay output sections.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_011__coverage-stamp-in-replay.md`

## Acceptance criteria
- replay input/output coverage contract points are explicit.
- required-mode fail-closed behavior is explicit.
- PASS + FAIL-CLOSED examples included.

## STOP conditions
- Stop if replay would silently continue on required missing coverage.
- Stop if output format cannot be made deterministic.

## Determinism notes
- Replay coverage output must be stable across repeated runs for identical inputs.
- Canonical ordering rules from TASK_PHASE2D_008 apply.
- Excluded: host-specific absolute paths in logs.
