# TASK_215 — Evidence path audit task/branch alignment

SPEC_EXPECTED: CODE

## Intent
Audit evidence paths to ensure alignment with task IDs and branch naming conventions.

## Acceptance criteria
- Helper validates `docs/dev/evidence/TASK_###/` and branch `TASK_###` alignment.
- Produces deterministic pass/fail output.
- Deterministic tests cover valid and invalid mappings.

## Files allowed to touch
- system/tools/evidence_path_audit.sh
- system/tests/test_evidence_path_audit.sh
- docs/dev/evidence/TASK_215/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_215/TESTS.txt
- docs/dev/evidence/TASK_215/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_215/DIFF_STAT.txt
- docs/dev/evidence/TASK_215/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if helper requires reading or writing forbidden hot files.
