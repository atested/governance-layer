# TASK_160__queue_drift_scan_optional_json_machine_output.md

TASK_ID: TASK_160
Title: [External usability next] queue_drift_scan optional JSON machine output
Executor: Codex
Owner/Gate: Greg
Branch: codex/TASK_160
Status: Ready
Dependencies: TASK_150
Bucket: External Usability Next

## Goal
Add optional machine-readable `queue_drift_scan.json` emission alongside `queue_drift_scan.txt` in release-gate proof-bundle outputs, with deterministic schema `queue_drift_scan_v1` and stable digest behavior.

## Preconditions
- `release-gate.sh` may emit `queue_drift_scan.txt` in proof-bundle output.
- `system/scripts/queue-drift-scan.py` exists on origin/main.

## Files allowed to touch
- system/scripts/release-gate.sh
- tests/test_queue_drift_scan_json_optional.sh
- docs/dev/evidence/TASK_160/**

## Files forbidden to touch
- system/scripts/queue-drift-scan.py
- docs/dev/WORK_QUEUE.md
- Any file not listed in Files allowed to touch

## Output expectations (Done)
- When queue-drift scan text output is present, release-gate also emits `queue_drift_scan.json` with deterministic schema/version and text digest.
- Regression test proves deterministic JSON digest behavior and additive optional semantics.

## Deterministic test plan
1. Run `tests/test_queue_drift_scan_json_optional.sh`.
2. Assert optional JSON emission with schema/version and stable digest when text output is present.
3. Assert additive optional behavior when queue-drift output is unavailable.

## Evidence required
- docs/dev/evidence/TASK_160/TESTS.txt

## STOP conditions
- Stop if queue-drift JSON emission requires changing `queue-drift-scan.py` (outside allowlist).
- Stop if changes spill outside allowlist.
- Stop if optional behavior becomes required/gating.

## Return format
1) Summary
2) Files changed
3) Optional JSON emission behavior
4) Test command(s) and exit codes
