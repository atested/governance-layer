# TASK_194 — Evidence bundle linter required files and hot-file scan

SPEC_EXPECTED: CODE

## Intent
Create a deterministic linter that validates evidence bundles contain required artifacts and that recorded diffs do not touch hot files.

## Acceptance criteria
- Provide a linter utility and deterministic test coverage.
- Linter checks required evidence files exist (`TESTS.txt`, `DIFF_NAME_ONLY.txt`, `DIFF_STAT.txt`, `HOTFILE_SCAN.txt`).
- Linter fails when hot-file matches are present in diff listings.

## Files allowed to touch
- system/tools/evidence_bundle_lint.sh
- system/tests/test_evidence_bundle_lint.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_194/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_194/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_194/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_194/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_194/HOTFILE_SCAN.txt

## Determinism expectations
- Run test twice and record matching stdout SHA256 values.

## STOP rules
- STOP if implementation requires touching hot files or WORK_QUEUE/ASSIGNMENTS.
