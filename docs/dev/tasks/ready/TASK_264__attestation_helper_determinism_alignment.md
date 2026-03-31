# TASK_264 — Attestation helper determinism alignment

SPEC_EXPECTED: CODE

## Intent
Standardize deterministic helper usage across current-main attestation/proof export/verify tests where equivalent cases still use divergent setup or hashing patterns. Keep scope bounded to existing merged helper/test behavior.

## Acceptance criteria
- Deterministic helper usage pattern aligned across touched attestation/proof tests.
- Equivalent deterministic assertions use shared helper conventions.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing helper/test behavior.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- docs/dev/evidence/TASK_264/**

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
- docs/dev/evidence/TASK_264/TESTS.txt
- docs/dev/evidence/TASK_264/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_264/DIFF_STAT.txt
- docs/dev/evidence/TASK_264/HOTFILE_SCAN.txt

## Determinism expectations
- Stable deterministic helper usage on touched attestation/proof tests.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed helper and directly adjacent test surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
