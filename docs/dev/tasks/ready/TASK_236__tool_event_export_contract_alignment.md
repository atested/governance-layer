# TASK_236 — Tool-event export contract alignment

SPEC_EXPECTED: CODE

## Intent
Align machine-readable export output contracts for current-main tool-event bundle export behavior. Standardize stable field ordering, id/digest/reason usage, and fail-closed malformed-input behavior where current-main export output still varies. Keep scope bounded to existing merged export behavior.

## Acceptance criteria
- Deterministic output structure across touched export surfaces.
- Stable ordering in machine-readable outputs where ordering applies.
- Stable id/digest/reason usage for touched export outputs.
- Negative controls for malformed inputs are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event export behavior and tests.

## Files allowed to touch
- scripts/attest/export_tool_event_bundle.py
- system/tests/**
- docs/dev/evidence/TASK_236/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_236/TESTS.txt
- docs/dev/evidence/TASK_236/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_236/DIFF_STAT.txt
- docs/dev/evidence/TASK_236/HOTFILE_SCAN.txt

## Determinism expectations
- Stable ordering and id/digest/reason output behavior on touched export surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-event export surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

