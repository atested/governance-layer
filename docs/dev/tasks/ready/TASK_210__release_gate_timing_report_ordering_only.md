# TASK_210 — Release-gate timing report ordering only

SPEC_EXPECTED: CODE

## Intent
Create deterministic timing-order report for release-gate logs using step ordering rather than wall-clock values.

## Acceptance criteria
- Parser emits stable step sequence and ordinal durations.
- No dependence on machine clock or runtime jitter.
- Deterministic test verifies identical output across repeated runs.

## Files allowed to touch
- system/tools/release_gate_timing_report.sh
- system/tests/test_release_gate_timing_report.sh
- docs/dev/evidence/TASK_210/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_210/TESTS.txt
- docs/dev/evidence/TASK_210/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_210/DIFF_STAT.txt
- docs/dev/evidence/TASK_210/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if implementation requires editing `system/scripts/release-gate.sh`.
