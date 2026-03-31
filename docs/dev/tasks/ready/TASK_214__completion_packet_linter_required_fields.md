# TASK_214 — Completion packet linter required fields

SPEC_EXPECTED: CODE

## Intent
Add linter that validates completion packet structure and required fields.

## Acceptance criteria
- Linter enforces mandatory keys and ordered sections.
- Produces stable fail messages for missing fields.
- Deterministic test verifies repeatable pass/fail outputs.

## Files allowed to touch
- system/tools/completion_packet_linter.sh
- system/tests/test_completion_packet_linter.sh
- docs/dev/evidence/TASK_214/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_214/TESTS.txt
- docs/dev/evidence/TASK_214/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_214/DIFF_STAT.txt
- docs/dev/evidence/TASK_214/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if packet contract cannot be checked without hot-file edits.
