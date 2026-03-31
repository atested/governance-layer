# TASK_233 — Tool-catalog query edge alignment

SPEC_EXPECTED: CODE

## Intent
Align edge-case query behavior and machine-readable output contracts across current-main tool-catalog query/get/list flows. Standardize stable ordering, id/digest/reason usage, and fail-closed malformed-input behavior while keeping scope bounded to existing tool-catalog store behavior and tests.

## Acceptance criteria
- Deterministic output structure across touched tool-catalog query/get/list surfaces.
- Stable ordering in machine-readable outputs where ordering applies.
- Negative controls for malformed inputs are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-catalog store behavior and tests.

## Files allowed to touch
- mcp/tool_catalog_store.py
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_233/**

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
- docs/dev/evidence/TASK_233/TESTS.txt
- docs/dev/evidence/TASK_233/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_233/DIFF_STAT.txt
- docs/dev/evidence/TASK_233/HOTFILE_SCAN.txt

## Determinism expectations
- Stable ordering and reason/id/digest output behavior on touched query surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-catalog query/store surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-catalog files.
