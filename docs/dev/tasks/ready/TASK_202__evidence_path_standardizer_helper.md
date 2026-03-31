# TASK_202 — Evidence path standardizer helper

SPEC_EXPECTED: CODE

## Intent
Add helper ensuring evidence paths match required batch/task directory conventions.

## Acceptance criteria
- Utility validates and normalizes expected evidence path structure.
- Deterministic test covers valid and invalid layouts.

## Files allowed to touch
- system/tools/evidence_path_standardizer.sh
- system/tests/test_evidence_path_standardizer.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_202/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_202/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_202/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_202/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_202/HOTFILE_SCAN.txt

## Determinism expectations
- Repeat run output digests must match.

## STOP rules
- STOP if normalizer requires touching evidence outside allowlisted paths.
