# TASK_254 — Attestation export output alignment

SPEC_EXPECTED: CODE

## Intent
Align remaining machine-readable output shapes across current-main attestation/proof export utilities where ordering, key presence, or digest/reason formatting still differs. Keep scope bounded to existing merged export behavior and tests.

## Acceptance criteria
- Deterministic output structure and stable ordering across touched export-side surfaces.
- Stable reason/digest/id formatting across touched export outputs.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing attestation/proof export behavior and tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_254/**

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
- docs/dev/evidence/TASK_254/TESTS.txt
- docs/dev/evidence/TASK_254/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_254/DIFF_STAT.txt
- docs/dev/evidence/TASK_254/HOTFILE_SCAN.txt

## Determinism expectations
- Stable output ordering and field-shape behavior for touched export-side surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed export-side surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
