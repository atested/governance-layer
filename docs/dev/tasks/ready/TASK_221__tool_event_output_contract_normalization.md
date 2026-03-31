# TASK_221 — Tool-event output contract normalization

SPEC_EXPECTED: CODE

## Intent
Normalize machine-readable output contracts across current-main tool-event lifecycle utilities and adjacent attest/export/verify flows, with deterministic structure and fail-closed malformed-input handling.

## Acceptance criteria
- Deterministic output structure and stable field ordering across touched tool-event lifecycle outputs.
- Reason/id/digest usage is normalized where current-main outputs diverge.
- Malformed-input handling is fail-closed with stable negative controls.
- Scope remains bounded to current merged tool-event lifecycle surfaces.

## Files allowed to touch
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_221/**

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
- docs/dev/evidence/TASK_221/TESTS.txt
- docs/dev/evidence/TASK_221/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_221/DIFF_STAT.txt
- docs/dev/evidence/TASK_221/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic output structure/order for touched tool-event contracts.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if tests require pre-existing `out/` artifacts not created by the test.
- STOP if scope drifts outside the listed tool-event lifecycle surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-event files.
