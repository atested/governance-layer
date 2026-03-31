# TASK_199 — Release-gate summary parser stable counts

SPEC_EXPECTED: CODE

## Intent
Implement deterministic parser utility producing stable PASS/FAIL/EXIT summary lines for evidence transcripts.

## Acceptance criteria
- Utility parses release-gate log files without network access.
- Emits stable `PASS_LINES=`, `FAIL_LINES=`, and `EXIT=` fields.
- Deterministic test validates parser output.

## Files allowed to touch
- system/tools/release_gate_summary_parser.sh
- system/tests/test_release_gate_summary_parser.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_199/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_199/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_199/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_199/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_199/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run parser stdout SHA256 must match.

## STOP rules
- STOP if parser requires modifying release-gate implementation.
