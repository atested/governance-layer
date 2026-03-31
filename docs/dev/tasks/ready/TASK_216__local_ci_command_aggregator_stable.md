# TASK_216 — Local CI command aggregator stable

SPEC_EXPECTED: CODE

## Intent
Provide one deterministic local command that runs minimal checks and emits stable summary output.

## Acceptance criteria
- Wrapper executes checks in fixed order.
- Emits stable pass/fail/exit summary lines.
- Deterministic test validates run1/run2 equality.

## Files allowed to touch
- system/tools/local_ci_aggregator.sh
- system/tests/test_local_ci_aggregator.sh
- docs/dev/evidence/TASK_216/**

## Files forbidden to touch
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_216/TESTS.txt
- docs/dev/evidence/TASK_216/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_216/DIFF_STAT.txt
- docs/dev/evidence/TASK_216/HOTFILE_SCAN.txt

## Determinism expectations
- run1/run2 stdout SHA256 must match.

## STOP rules
- STOP if implementation requires touching hot files.
