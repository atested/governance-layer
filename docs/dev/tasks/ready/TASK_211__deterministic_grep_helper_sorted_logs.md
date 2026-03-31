# TASK_211 — Deterministic grep helper sorted logs

SPEC_EXPECTED: CODE

## Intent
Provide deterministic grep wrapper that normalizes match ordering for log evidence.

## Acceptance criteria
- Wrapper accepts pattern and input file(s).
- Output lines are stable and sorted under `LC_ALL=C`.
- Deterministic test verifies repeated output equality.

## Files allowed to touch
- system/tools/deterministic_grep.sh
- system/tests/test_deterministic_grep.sh
- docs/dev/evidence/TASK_211/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_211/TESTS.txt
- docs/dev/evidence/TASK_211/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_211/DIFF_STAT.txt
- docs/dev/evidence/TASK_211/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if helper requires non-portable shell features.
