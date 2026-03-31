# TASK_103__replay_drift_hardening_controlled_registry_swap_.md

TASK_ID: TASK_103
Title: Replay drift hardening: controlled registry swap test (T-REPLAY-004 starter)
Executor: CODEX
Branch: codex/TASK_103
Status: Ready
Dependencies: []

## Goal
Add a deterministic test harness that replays a record under a controlled capability registry hash mismatch scenario and fails closed with the expected exit code.

## Non-goals
No dynamic network fetch. No broad refactor.

## Files allowed to touch
- docs/dev/evidence/TASK_103/**
- scripts/replay-record.py
- tests/**
- capabilities/**
- docs/dev/EPIC_SIGNING.md

## Files forbidden to touch
[]

## Procedure
Create a controlled fixture/alternate registry; confirm failure mode; evidence.

## Acceptance criteria
Replay detects registry drift and exits fail-closed with stable code/message.

## Evidence required
TESTS.txt shows the drift case and exit markers.

## Return format
Summary + fixtures used.
