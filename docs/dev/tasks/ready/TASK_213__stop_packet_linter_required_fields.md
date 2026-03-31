# TASK_213 — STOP packet linter required fields

SPEC_EXPECTED: CODE

## Intent
Add linter for STOP PACKET format presence and field completeness.

## Acceptance criteria
- Linter validates required STOP PACKET lines are present.
- Returns stable nonzero exit with deterministic reason for missing fields.
- Deterministic test covers pass/fail cases.

## Files allowed to touch
- system/tools/stop_packet_linter.sh
- system/tests/test_stop_packet_linter.sh
- docs/dev/evidence/TASK_213/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_213/TESTS.txt
- docs/dev/evidence/TASK_213/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_213/DIFF_STAT.txt
- docs/dev/evidence/TASK_213/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if linter requires hot-file edits.
