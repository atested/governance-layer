# TASK_198 — Wrong execution root operator note

SPEC_EXPECTED: CODE

## Intent
Document canonical WRONG_EXECUTION_ROOT handling and STOP PACKET shape for operators.

## Acceptance criteria
- Add concise operator note with deterministic examples.
- Include STOP PACKET field expectations.

## Files allowed to touch
- docs/design/wrong-execution-root-operator-note.md
- system/tests/test_wrong_execution_root_doc.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_198/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_198/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_198/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_198/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_198/HOTFILE_SCAN.txt

## Determinism expectations
- Validation grep checks run twice and hash-equal.

## STOP rules
- STOP if documentation changes would require ASSIGNMENTS/WORK_QUEUE edits.
