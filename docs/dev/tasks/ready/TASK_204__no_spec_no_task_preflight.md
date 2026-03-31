# TASK_204 — No spec no task preflight

SPEC_EXPECTED: CODE

## Intent
Create preflight utility that blocks task execution when required task specs are missing.

## Acceptance criteria
- Utility checks for missing specs in ready/proposed sets deterministically.
- Emits stable STOP reason and nonzero exit when spec missing.

## Files allowed to touch
- system/tools/no_spec_no_task_preflight.sh
- system/tests/test_no_spec_no_task_preflight.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_204/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_204/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_204/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_204/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_204/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run output SHA256 must match.

## STOP rules
- STOP if preflight logic requires touching WORK_QUEUE or ASSIGNMENTS.
