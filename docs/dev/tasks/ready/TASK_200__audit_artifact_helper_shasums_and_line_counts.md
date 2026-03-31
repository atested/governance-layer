# TASK_200 — Audit artifact helper shasums and line counts

SPEC_EXPECTED: CODE

## Intent
Create helper that emits deterministic artifact hashes and line-count metadata for evidence imports.

## Acceptance criteria
- Utility outputs sorted SHA256 + line-count table.
- Handles missing files deterministically with nonzero exit.
- Deterministic test verifies output stability.

## Files allowed to touch
- system/tools/audit_artifact_helper.sh
- system/tests/test_audit_artifact_helper.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_200/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_200/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_200/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_200/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_200/HOTFILE_SCAN.txt

## Determinism expectations
- Run twice with matching digest.

## STOP rules
- STOP if helper requires external tooling not present in repo runtime.
