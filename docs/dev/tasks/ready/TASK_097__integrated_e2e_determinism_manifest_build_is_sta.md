# TASK_097__integrated_e2e_determinism_manifest_build_is_sta.md

TASK_ID: TASK_097
Title: Integrated E2E determinism: manifest build is stable across runs
Executor: CODEX
Branch: codex/TASK_097
Status: Ready
Dependencies: []

## Goal
Ensure build-manifest output (MANIFEST.json and any build_manifest.txt/log) is deterministic across two runs with identical inputs.

## Non-goals
No new manifest fields unless required for determinism.

## Files allowed to touch
- docs/dev/evidence/TASK_097/**
- scripts/policy-eval.py
- scripts/replay-record.py
- scripts/verify-record.py
- scripts/verify-chain.py
- tests/**
## Files forbidden to touch
[]

## Procedure
1) Confirm missing harness paths are removed: do not reference scripts/attest/** or tests/test_integrated_e2e_full.sh.
2) Define a deterministic build-manifest artifact derived from existing stable fields:
   - Use stable hashes already produced by the system (record_hash, cap_registry_hash, request_hash, normalized_args, reason_codes ordering, etc.).
   - The manifest must not include absolute paths, timestamps, or non-deterministic ordering.
   - Serialize in canonical deterministic form (stable key order and stable list ordering).
3) Implement manifest generation in an existing deterministic path:
   - Preferred: add a function in scripts/policy-eval.py (or scripts/replay-record.py) that emits MANIFEST.json for a fixed input set.
4) Add/extend a test under tests/ that:
   - Generates the manifest twice from identical inputs
   - Asserts byte-identical output (or sha256 identical).
5) Evidence:
   - docs/dev/evidence/TASK_097/TESTS.txt with $ commands and [exit=...] markers showing two identical manifest hashes and a passing test run.
## Acceptance criteria


- Manifest output is deterministic across two runs with identical inputs (byte-identical or identical sha256).
- Manifest content is derived only from stable system fields; no absolute paths or timestamps.
- Test added/updated under tests/ demonstrates determinism and fails closed on drift.
## Evidence required


- docs/dev/evidence/TASK_097/TESTS.txt showing:
  - two runs producing identical manifest hash
  - test command + exit markers
## Return format
Return:
- Files changed
- Manifest definition (fields included and ordering rules)
- Test name + command
- Two identical manifest hashes from evidence
