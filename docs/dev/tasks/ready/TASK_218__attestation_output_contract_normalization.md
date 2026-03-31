# TASK_218 — Attestation output contract normalization

SPEC_EXPECTED: CODE

## Intent
Normalize machine-readable output contracts across current-main attestation/proof utilities under `scripts/attest/` for deterministic structure and fail-closed malformed-input handling, without adding new product features.

## Acceptance criteria
- Output structure and field ordering are deterministic for touched utilities.
- Reason/id/digest usage is normalized where contracts currently diverge.
- Malformed-input handling is fail-closed with stable negative controls.
- Scope stays bounded to existing merged utilities and tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_218/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_218/TESTS.txt
- docs/dev/evidence/TASK_218/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_218/DIFF_STAT.txt
- docs/dev/evidence/TASK_218/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic output structure/order for touched contracts.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if tests depend on pre-existing `out/` artifacts not created by the test.
- STOP if scope drifts beyond `scripts/attest/` and `system/tests/`.

## Constraints
- No merge work.
- No MCP/server integration.
- No reporting-row onboarding.
- No doctrine changes.
