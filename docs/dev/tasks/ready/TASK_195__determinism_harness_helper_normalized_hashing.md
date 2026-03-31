# TASK_195 — Determinism harness helper normalized hashing

SPEC_EXPECTED: CODE

## Intent
Add a reusable deterministic hashing helper that normalizes unstable output fragments before hash comparison.

## Acceptance criteria
- Helper accepts input files and emits normalized SHA256 deterministically.
- Normalization strips absolute temp paths and trailing whitespace.
- Deterministic test verifies run1/run2 hash equivalence.

## Files allowed to touch
- system/tools/determinism_harness.sh
- system/tests/test_determinism_harness.sh
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_195/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_195/TESTS.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_195/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_195/DIFF_STAT.txt
- docs/dev/evidence/TASK_RESTOCK_AND_IMPLEMENT__2026-02-28/TASK_195/HOTFILE_SCAN.txt

## Determinism expectations
- Two-run output digest equality is mandatory.

## STOP rules
- STOP if helper needs external network dependencies or hot-file edits.
