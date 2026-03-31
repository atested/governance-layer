# TASK_099__integrated_e2e_determinism_signing_outputs_conta.md

TASK_ID: TASK_099
Title: Integrated E2E determinism: signing outputs contain no timestamps or nondeterministic fields
Executor: CODEX
Branch: codex/TASK_099
Status: Ready
Dependencies: []

## Goal
Ensure sign-records outputs are stable across runs and do not embed timestamps, random nonces, or machine-dependent paths into signed payloads.

## Non-goals
No security audit; determinism only.

## Files allowed to touch
- docs/dev/evidence/TASK_099/**
- scripts/policy-eval.py
- scripts/verify-record.py
- tests/test_signing_determinism.sh

## Files forbidden to touch
[]

## Procedure
1) Ensure record_hash/signing preimage excludes non-deterministic fields (timestamps, UUIDs, path-like metadata) while preserving existing canonical semantics for stable fields.
2) Implement deterministic signing-preimage sanitization in the emit path and mirror the same logic in verification.
3) Preserve backward compatibility for existing records where feasible (e.g. verifier accepts legacy preimage/hash behavior) while making new outputs deterministic.
4) Add a deterministic signing test under tests/ that:
   - runs the relevant flow multiple times
   - confirms identical per-record hash/signing outputs across runs
   - confirms verifier still passes
5) Write evidence:
   - docs/dev/evidence/TASK_099/TESTS.txt with exact commands and [exit=...] markers, including hash outputs from repeated runs.

## Acceptance criteria
- Newly produced signing/record outputs do not depend on timestamps, random nonces, or machine-specific paths.
- Repeated runs over identical inputs produce identical deterministic hashes/signing outputs.
- verify-record continues to validate expected records (including legacy compatibility behavior if implemented).
- tests/test_signing_determinism.sh passes.

## Evidence required
- docs/dev/evidence/TASK_099/TESTS.txt showing:
  - signing determinism test command(s)
  - [exit=...] markers
  - repeated-run hash outputs demonstrating equality

## Return format
Return:
- files changed
- which fields were excluded/sanitized from the signing preimage and why
- compatibility behavior for legacy records (if any)
- test command + summary output
