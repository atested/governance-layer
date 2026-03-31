# TASK_249 — Attestation verify reason alignment

SPEC_EXPECTED: CODE

## Intent
Align verify-side reason codes and fail-closed output shape where current-main attestation/proof verify utilities still diverge in mismatch or invalid-input handling. Keep scope bounded to existing merged verify behavior and tests.

## Acceptance criteria
- Deterministic reason-coded outputs for touched verify-side mismatch and invalid-input paths.
- Fail-closed contract shape is stable across touched verify utilities.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing attestation/proof verify behavior and tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_249/**

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
- docs/dev/evidence/TASK_249/TESTS.txt
- docs/dev/evidence/TASK_249/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_249/DIFF_STAT.txt
- docs/dev/evidence/TASK_249/HOTFILE_SCAN.txt

## Determinism expectations
- Stable reason-coded output behavior for touched verify-side surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed attestation/proof verify surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
