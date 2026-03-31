# TASK_PHASE2D_010 — Coverage Stamp in verify-chain

## Scope
Specify verify-chain contract for chain-level coverage stamp validation and reporting.

Contract points:
- verify-chain validates coverage stamp presence and canonical ordering per record.
- verify-chain emits aggregate coverage summary across chain records.
- Required-chain mode fails closed on missing required coverage stamp in any record.

Examples:
- PASS: all records include valid canonical coverage stamp; summary status `complete`; rc=0.
- FAIL-CLOSED: one record missing required stamp; emit `COVERAGE_STAMP_MISSING`; rc!=0.

## Non-goals
- No changes to signature/hash validation logic.
- No changes to chain storage format.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_010__coverage-stamp-in-verify-chain.md`

## Acceptance criteria
- Per-record and chain-aggregate coverage checks are explicit.
- Required-mode fail-closed behavior is explicit.
- PASS + FAIL-CLOSED examples included.

## STOP conditions
- Stop if chain-level behavior would mask missing per-record coverage.
- Stop if aggregate status is not deterministic.

## Determinism notes
- Aggregate ordering follows record order and canonical surface order.
- Excluded: non-contractual debug traces.
