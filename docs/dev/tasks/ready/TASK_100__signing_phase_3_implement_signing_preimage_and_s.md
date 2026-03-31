# TASK_100__signing_phase_3_implement_signing_preimage_and_s.md

TASK_ID: TASK_100
Title: Signing Phase 3: implement signing_preimage and signature write path in policy-eval
Executor: CODEX
Branch: codex/TASK_100
Status: Ready
Dependencies: []

## Goal
Implement Phase 3 signing emit path per docs/dev/EPIC_SIGNING.md: compute signing_preimage, record_hash (sha256:...), signature (Ed25519), signing_key_id, fail-closed when key missing.

## Non-goals
No key rotation UI. No network key fetch. No crypto strength guarantees beyond correct Ed25519 usage and determinism.

## Files allowed to touch
- docs/dev/evidence/TASK_100/**
- scripts/policy-eval.py
- tests/test_signing_emit.sh
- docs/dev/tasks/ready/TASK_100__signing_phase_3_implement_signing_preimage_and_s.md

## Files forbidden to touch
[]

## Procedure
Implement signing as specified; add deterministic tests; write evidence with commands and exits.

## Acceptance criteria
Emitted records include signature + signing_key_id when Phase 3 enabled; verify tools accept; missing key fails closed.

## Evidence required
TESTS.txt includes commands demonstrating success and fail-closed behavior.

## Return format
Summary + changed files + how to run tests.
