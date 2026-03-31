# TASK_PHASE2D_004 — verify-record Coverage Output

## Scope
Specify CLI output contract for verify-record coverage summary, including formatting and reason codes.

Output section contract:
- Section header: `Coverage Summary`
- Per-surface lines in canonical order
- Summary line with overall status

Formatting rules:
- Stable, line-oriented text format.
- Canonical field order per line: surface_id, observation, enforcement, provenance, status.
- Deterministic separators and capitalization.

Reason codes (required):
- `COVERAGE_STAMP_MISSING`
- `COVERAGE_STAMP_PARTIAL`
- `COVERAGE_STAMP_MALFORMED`

## Non-goals
- No runtime CLI implementation in this task.
- No changes to non-coverage verify-record output sections.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_004__verify-record-coverage-output.md`

## Acceptance criteria
- Coverage section layout is explicit.
- Stable ordering and deterministic formatting rules are explicit.
- Required reason codes for missing/partial/malformed are explicit.

## STOP conditions
- Stop if output contract conflicts with existing mandated CLI output invariants.
- Stop if reason-code taxonomy is incomplete for missing/partial cases.

## Determinism notes
- Output must be stable for identical input artifacts.
- Excluded: terminal color, tty-width formatting, or localized message variants.
