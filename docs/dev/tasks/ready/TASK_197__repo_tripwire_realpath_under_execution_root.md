# TASK_197 — Repo tripwire realpath under execution root

SPEC_EXPECTED: CODE

## Intent
Add a deterministic tripwire utility to assert resolved paths remain under the required execution root.

## Acceptance criteria
- Utility rejects paths escaping the execution root.
- Deterministic tests cover pass/fail cases.

## Files allowed to touch
- system/tools/repo_tripwire.sh
- system/tests/test_repo_tripwire.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_197/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_197/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_197/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_197/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_197/HOTFILE_SCAN.txt

## Determinism expectations
- Run twice with matching output digests.

## STOP rules
- STOP if tripwire requires editing runtime scripts listed as hot files.
