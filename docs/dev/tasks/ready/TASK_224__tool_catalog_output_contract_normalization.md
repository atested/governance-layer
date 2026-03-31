# TASK_224 — Tool-catalog output contract normalization

SPEC_EXPECTED: CODE

## Intent
Normalize machine-readable output contracts across current-main tool-catalog store and adjacent export/verify flows. Standardize stable field ordering, reason/id/digest usage, and fail-closed malformed-input behavior where current-main tool-catalog outputs differ.

## Acceptance criteria
- Deterministic output structure across touched tool-catalog surfaces.
- Stable ordering in machine-readable outputs where ordering applies.
- Negative controls for malformed inputs are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-catalog surfaces; no new product features.

## Files allowed to touch
- mcp/tool_catalog_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_224/**

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
- docs/dev/evidence/TASK_224/TESTS.txt
- docs/dev/evidence/TASK_224/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_224/DIFF_STAT.txt
- docs/dev/evidence/TASK_224/HOTFILE_SCAN.txt

## Determinism expectations
- Stable machine-readable output ordering and reason/id/digest usage across touched surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if tests require pre-existing `out/` artifacts not created by the test.
- STOP if scope drifts outside listed tool-catalog surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-catalog files.
