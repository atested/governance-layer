# TASK_239 — Attestation/proof output unification

SPEC_EXPECTED: CODE

## Intent
Unify remaining machine-readable output shapes across current-main attestation/proof utilities that are still inconsistent after prior hardening passes. Standardize stable ordering, id/digest/reason usage, and fail-closed malformed-input behavior. Keep scope bounded to existing `scripts/attest` tools and their direct tests.

## Acceptance criteria
- Deterministic output structure across touched attestation/proof utilities.
- Stable ordering in machine-readable outputs where ordering applies.
- Stable id/digest/reason usage for touched outputs.
- Negative controls for malformed inputs are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing `scripts/attest` tools and direct tests.

## Files allowed to touch
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_239/**

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
- docs/dev/evidence/TASK_239/TESTS.txt
- docs/dev/evidence/TASK_239/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_239/DIFF_STAT.txt
- docs/dev/evidence/TASK_239/HOTFILE_SCAN.txt

## Determinism expectations
- Stable ordering and id/digest/reason output behavior on touched attestation/proof surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed attestation/proof utility surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

