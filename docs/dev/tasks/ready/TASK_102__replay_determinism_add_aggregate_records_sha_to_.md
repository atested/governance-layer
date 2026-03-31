# TASK_102__replay_determinism_add_aggregate_records_sha_to_.md

TASK_ID: TASK_102
Title: Replay determinism: add aggregate RECORDS_SHA to replay output (stable ordering)
Executor: CODEX
Branch: codex/TASK_102
Status: Ready
Dependencies: []

## Goal
Ensure replay tooling computes and prints a path-independent aggregate (RECORDS_SHA) from per-record stable identifiers; sort deterministically.

## Non-goals
No UI. No new external deps.

## Files allowed to touch
- docs/dev/evidence/TASK_102/**

## Files forbidden to touch
[]

## Procedure
Run the existing RECORDS_SHA determinism test and capture a clean transcript in `docs/dev/evidence/TASK_102/TESTS.txt` (commands and `[exit=...]` markers only).

## Acceptance criteria
Existing determinism test passes and evidence shows identical RECORDS_SHA across runs with no code changes.

## Evidence required
TESTS.txt shows the determinism test command, pass output, identical RECORDS_SHA values, and a final `[exit=0]` for the test command.

## Return format
Summary + test command.
