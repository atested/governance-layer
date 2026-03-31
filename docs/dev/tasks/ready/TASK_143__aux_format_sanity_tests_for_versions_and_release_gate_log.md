# TASK_143__aux_format_sanity_tests_for_versions_and_release_gate_log.md

TASK_ID: TASK_143
Title: [External usability] Auxiliary format sanity tests for versions.txt and release_gate_log.txt
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_143
Status: Ready
Dependencies: TASK_136
Bucket: External usability

## Goal
Add deterministic sanity tests ensuring versions.txt and release_gate_log.txt remain key=value lines with non-empty keys and no spacing around =.

## Non-goals
- Do not broaden scope beyond the task goal.
- Do not weaken fail-closed behavior or determinism guarantees.
- Do not modify unrelated workflow/queue specs.

## Files allowed to touch
- system/scripts/release-gate.sh
- tests/test_release_gate_aux_file_formats.sh
- docs/dev/evidence/TASK_143/**

## Files forbidden to touch
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_143/TESTS.txt` with commands and `[exit=...]` markers.
- Deterministic test output digest/equality checks pass across two runs.

## Deterministic test plan
1. Run the task-specific test runner twice with fixed RELEASE_GATE_RUN_ID values.
2. Assert stable PASS markers and digest equality for the contract-reporting output.
3. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_143/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If origin/main already contains the full tests/behavior, stop and convert to reconcile/provenance closeout.
- If required changes fall outside the allowlist, stop and request a minimal spec allowlist adjustment.

## Return format
1) Summary
2) Files changed
3) Determinism proof
4) Test command(s) and exit codes
