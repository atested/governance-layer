# TASK_101__signing_phase_3_implement_verifier_support_for_s.md

TASK_ID: TASK_101
Title: Signing Phase 3: implement verifier support for signature and signing_key_id
Executor: CODEX
Branch: codex/TASK_101
Status: Ready
Dependencies: []

## Goal
Extend verify-record / verify-chain to validate signature using signing_preimage and enforce signing_key_id thumbprint match as specified.

## Non-goals
No key management UI. No registry drift work.

## Files allowed to touch
- docs/dev/evidence/TASK_101/**
- scripts/policy-eval.py
- scripts/verify-record.py
- scripts/verify-chain.py
- scripts/replay-record.py
- tests/**
- docs/dev/EPIC_SIGNING.md

## Files forbidden to touch
[]

## Procedure
Implement signature verify; add tests; evidence.

## Acceptance criteria
Valid signature passes; tampered signature fails; signing_key_id mismatch fails; deterministic output.

## Evidence required
Commands and exits showing pass/fail cases.

## Return format
Summary + tests.
