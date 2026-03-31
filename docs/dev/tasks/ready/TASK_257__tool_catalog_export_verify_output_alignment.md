# TASK_257 — Tool-catalog export/verify output alignment

SPEC_EXPECTED: CODE

## Intent
Align remaining machine-readable output shapes across current-main tool-catalog export/verify utilities where ordering, key presence, or digest/reason formatting still differs. Keep scope bounded to existing merged export/verify behavior and tests.

## Acceptance criteria
- Deterministic output structure and stable ordering across touched export/verify surfaces.
- Stable reason/digest/id formatting across touched export/verify outputs.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-catalog export/verify behavior and tests.

## Files allowed to touch
- mcp/tool_catalog_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_257/**

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
- docs/dev/evidence/TASK_257/TESTS.txt
- docs/dev/evidence/TASK_257/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_257/DIFF_STAT.txt
- docs/dev/evidence/TASK_257/HOTFILE_SCAN.txt

## Determinism expectations
- Stable output ordering and field-shape behavior for touched export/verify surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-catalog export/verify surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
