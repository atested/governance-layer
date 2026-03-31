# TASK_201 — CI-like local minimal validation command

SPEC_EXPECTED: CODE

## Intent
Provide a single deterministic local command that runs minimal required checks for batch validation.

## Acceptance criteria
- One wrapper command executes required checks in stable order.
- Emits deterministic summary with pass/fail and exit.

## Files allowed to touch
- system/tools/local_ci_minimal.sh
- system/tests/test_local_ci_minimal.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_201/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_201/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_201/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_201/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_201/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run deterministic output required.

## STOP rules
- STOP if implementation requires touching hot files.
