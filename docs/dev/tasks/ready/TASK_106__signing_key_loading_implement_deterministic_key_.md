# TASK_106__signing_key_loading_implement_deterministic_key_.md

TASK_ID: TASK_106
Title: Signing key loading: implement deterministic key discovery and explicit failure modes
Executor: CODEX
Branch: codex/TASK_106
Status: Ready
Dependencies: []

## Goal
Implement key loading order per EPIC_SIGNING.md (env var, ~/.config path, etc.) and make failure modes explicit and stable.

## Non-goals
No key generation tooling beyond docs; no UI.

## Files allowed to touch
- docs/dev/evidence/TASK_106/**
- scripts/policy-eval.py
- docs/dev/EPIC_SIGNING.md
- tests/**

## Files forbidden to touch
[]

## Procedure
Implement load order; add tests; document dev setup; evidence.

## Acceptance criteria
Correct key loads; missing/invalid key fails closed deterministically.

## Evidence required
TESTS.txt shows deterministic failures and successes.

## Return format
Summary + setup notes.
