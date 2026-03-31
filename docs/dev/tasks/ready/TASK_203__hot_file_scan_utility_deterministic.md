# TASK_203 — Hot file scan utility deterministic

SPEC_EXPECTED: CODE

## Intent
Implement deterministic hot-file scanner utility for batch enforcement.

## Acceptance criteria
- Utility scans provided file list and exits nonzero on hot-file hits.
- Hot-file pattern list is explicit and stable.
- Deterministic test verifies pass/fail behavior.

## Files allowed to touch
- system/tools/hot_file_scan.sh
- system/tests/test_hot_file_scan.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_203/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_203/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_203/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_203/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_203/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run identical stdout digest required.

## STOP rules
- STOP if scanner requires editing hot files or global queue documents.
