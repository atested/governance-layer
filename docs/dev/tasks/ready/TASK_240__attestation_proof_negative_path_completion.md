# TASK_240 — Attestation/proof negative-path completion

SPEC_EXPECTED: CODE

## Intent
Complete remaining negative-path alignment across current-main attestation/proof utilities where malformed-input or mismatch cases still differ in error shape or reason coding. Keep work bounded to existing merged utilities and tests.

## Acceptance criteria
- Deterministic negative-path behavior across touched attestation/proof utilities.
- Stable reason-coded outputs where failures or mismatch states are emitted.
- Negative controls for malformed inputs and mismatch conditions are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged attestation/proof utilities and tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_240/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- mcp/tool_catalog_store.py
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_240/TESTS.txt
- docs/dev/evidence/TASK_240/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_240/DIFF_STAT.txt
- docs/dev/evidence/TASK_240/HOTFILE_SCAN.txt

## Determinism expectations
- Stable reason/digest/error-shape behavior on touched negative paths.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if alignment requires expansion into unrelated subsystems.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

