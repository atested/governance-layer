# TASK_284 — Tool-event filtered-slice support

SPEC_EXPECTED: CODE

## Intent
Extend current-main tool-event store behavior with one bounded deterministic filtered-slice capability for inspection of existing tool-event contents. The slice is selected from existing tool-event data only, without server integration and without introducing a new product surface beyond store/export/report behavior.

## Acceptance criteria
- Deterministic filtered-slice selection over existing tool-event data.
- Stable ordering for selected rows and digest/run identifiers.
- Slice filtering remains bounded to existing tool-event store fields.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.

## Files allowed to touch
- mcp/tool_event_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_284/**

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
- Reporting-enrollment surfaces.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_284/TESTS.txt
- docs/dev/evidence/TASK_284/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_284/DIFF_STAT.txt
- docs/dev/evidence/TASK_284/HOTFILE_SCAN.txt

## Determinism expectations
- Filtered slices are byte-stable and order-stable for identical tool-event state.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if slice behavior cannot remain bounded to existing tool-event data.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration.
