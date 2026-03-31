# TASK_105__verify_tooling_enforce_deterministic_reason_code.md

TASK_ID: TASK_105
Title: Verify tooling: enforce deterministic reason_code ordering in verify paths
Executor: CODEX
Branch: codex/TASK_105
Status: Ready
Dependencies: []

## Goal
Ensure verify tools enforce the canonical reason_code ordering (REASON_ORDER) deterministically and fail closed on mismatches.

## Non-goals
No policy changes; only verification strictness.

## Files allowed to touch
- docs/dev/evidence/TASK_105/**
- scripts/verify-record.py
- scripts/policy-eval.py
- tests/**

## Files forbidden to touch
[]

## Procedure
Add strict checks; tests; evidence.

## Acceptance criteria
Mismatch fails with stable exit; match passes; deterministic output.

## Evidence required
TESTS.txt shows both cases.

## Return format
Summary + tests.
