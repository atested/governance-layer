# TASK_104__manifest_determinism_generate_deterministic_mani.md

TASK_ID: TASK_104
Title: Manifest determinism: generate deterministic manifest sidecar from stable fields
Executor: CODEX
Branch: codex/TASK_104
Status: Ready
Dependencies: []

## Goal
Generate a deterministic MANIFEST.json derived only from stable record fields (hashes, normalized args, ordered reason codes), byte-identical across runs.

## Non-goals
No timestamps/paths. No new manifest fields unless required for determinism.

## Files allowed to touch
- docs/dev/evidence/TASK_104/**
- scripts/replay-record.py
- scripts/policy-eval.py
- tests/**

## Files forbidden to touch
[]

## Procedure
Implement manifest generation; add determinism test; evidence.

## Acceptance criteria
Manifest identical across runs; test passes.

## Evidence required
TESTS.txt includes two hashes and equality proof.

## Return format
Summary + test command.
