# TASK_150__queue_drift_scan_optional_file_semantics_test.md

TASK_ID: TASK_150
Title: [External CI correctness] queue_drift_scan optional-file semantics test
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_150
Status: Ready
Dependencies: TASK_136
Bucket: External CI correctness

## Goal
Add a deterministic test for `queue_drift_scan.txt` optional-file semantics: if present, it must be either non-empty human-readable output or the allowed sentinel line starting with `INFO: queue-drift-scan unavailable`.

## Non-goals
- Do not define or enforce a machine-readable parser for queue-drift-scan output.
- Do not make `queue_drift_scan.txt` required.
- Do not modify queue-drift-scan implementation unless strictly needed by this test and explicitly allowed (not expected).

## Preconditions
- `queue_drift_scan.txt` may be emitted by release-gate proof-bundle output.
- External contract documents sentinel semantics.

## Files allowed to touch
- tests/test_queue_drift_scan_optional_semantics.sh
- docs/dev/evidence/TASK_150/**

## Files forbidden to touch
- system/scripts/queue-drift-scan.py
- system/scripts/release-gate.sh
- docs/EXTERNAL_CONTRACTS.md
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- Deterministic validator accepts non-empty text output.
- Deterministic validator accepts sentinel form.
- Deterministic validator rejects empty file / malformed sentinel with stable marker.

## Success criteria
- Produces a CODE diff (at least one non-evidence path changed).
- Updates `docs/dev/evidence/TASK_150/TESTS.txt` with commands and `[exit=...]` markers.
- Transcript shows acceptable output and sentinel acceptance.

## Deterministic test plan
1. Validate a sample non-empty queue-drift text file.
2. Validate a sentinel-only file beginning with `INFO: queue-drift-scan unavailable`.
3. Negative control: empty file or malformed sentinel should fail with a stable marker.
4. Record commands, outputs, and `[exit=...]` markers in evidence.

## Evidence required
- docs/dev/evidence/TASK_150/TESTS.txt
- Transcript must include `$ ...` command lines and `[exit=...]` markers

## STOP conditions
- If required changes fall outside allowlist, stop and request a minimal spec allowlist adjustment.
- If contract wording is ambiguous, stop and request docs clarification before tightening tests.

## Return format
1) Summary
2) Files changed
3) Accepted/rejected optional-file semantics
4) Test command(s) and exit codes
