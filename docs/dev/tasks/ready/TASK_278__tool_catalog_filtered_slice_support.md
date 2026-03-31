# TASK_278 — Tool-catalog filtered-slice support

SPEC_EXPECTED: CODE

## Intent
Extend current-main tool-catalog store behavior with one bounded filtered-slice capability for deterministic inspection of catalog contents. The slice is selected from existing tool-catalog data only, with no server integration and no new product surface beyond store/export/report behavior. Output remains deterministic and machine-readable.

## Acceptance criteria
- Deterministic filtered-slice selection over existing tool-catalog data.
- Stable ordering for selected rows and ids/digests in outputs.
- Slice filtering remains bounded to existing catalog fields and store behavior.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.

## Files allowed to touch
- mcp/tool_catalog_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_278/**

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
- docs/dev/evidence/TASK_278/TESTS.txt
- docs/dev/evidence/TASK_278/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_278/DIFF_STAT.txt
- docs/dev/evidence/TASK_278/HOTFILE_SCAN.txt

## Determinism expectations
- Filtered slices are byte-stable and order-stable for identical catalog state.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if slice behavior cannot remain bounded to existing catalog data.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration.
