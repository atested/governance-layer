# TASK_261 — Tool-event export/verify shape consistency

SPEC_EXPECTED: CODE

## Intent
Complete remaining output-shape consistency across current-main tool-event export and verify flows so related success/error cases use stable comparable key/value structure. Keep scope bounded to existing merged export/verify behavior and tests.

## Acceptance criteria
- Deterministic output-shape consistency across touched export/verify success and failure cases.
- Stable comparable key/value structure across touched export and verify paths.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event export/verify behavior and tests.

## Files allowed to touch
- scripts/attest/export_tool_event_bundle.py
- scripts/attest/verify_tool_event_bundle.py
- system/tests/**
- docs/dev/evidence/TASK_261/**

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
- docs/dev/evidence/TASK_261/TESTS.txt
- docs/dev/evidence/TASK_261/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_261/DIFF_STAT.txt
- docs/dev/evidence/TASK_261/HOTFILE_SCAN.txt

## Determinism expectations
- Stable comparable key/value output structure on touched export/verify surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-event export/verify surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
