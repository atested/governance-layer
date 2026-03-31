# TASK_217 — Task spec self-checker required sections

SPEC_EXPECTED: CODE

## Intent
Add deterministic checker that validates required sections across ready task specs.

## Acceptance criteria
- Checker scans `docs/dev/tasks/ready` specs for required headings.
- Emits deterministic missing-section diagnostics.
- Deterministic test covers pass/fail behavior.

## Files allowed to touch
- system/tools/task_spec_self_checker.sh
- system/tests/test_task_spec_self_checker.sh
- docs/dev/evidence/TASK_217/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_217/TESTS.txt
- docs/dev/evidence/TASK_217/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_217/DIFF_STAT.txt
- docs/dev/evidence/TASK_217/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if checker requires modifying existing task specs outside task scope.
