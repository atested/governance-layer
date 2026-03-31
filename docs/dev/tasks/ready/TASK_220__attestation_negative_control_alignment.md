# TASK_220 — Attestation negative-control alignment

SPEC_EXPECTED: CODE

## Intent
Align negative-control behavior and error-shape expectations across current-main attestation/proof utilities so malformed-input and mismatch cases are consistently tested and easier to extend.

## Acceptance criteria
- Negative-control reason codes/error shapes are aligned across touched utilities/tests.
- Failure outputs are deterministic where applicable.
- Malformed-input and mismatch tests are self-contained and stable.
- Work stays bounded to existing merged attestation/proof utilities and tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_220/**

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
- docs/dev/evidence/TASK_220/TESTS.txt
- docs/dev/evidence/TASK_220/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_220/DIFF_STAT.txt
- docs/dev/evidence/TASK_220/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic reason-coded failure outputs for touched negative controls.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if consistent negative-control alignment cannot be achieved without expanding into unrelated subsystems.

## Constraints
- No merge work.
- No MCP/server integration.
- No reporting-row onboarding.
- No doctrine changes.
