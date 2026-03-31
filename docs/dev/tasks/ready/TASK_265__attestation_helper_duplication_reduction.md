# TASK_265 — Attestation helper duplication reduction

SPEC_EXPECTED: CODE

## Intent
Reduce duplicated setup/parsing logic across current-main attestation/proof tests only where shared helper extraction clearly lowers maintenance cost without broadening subsystem scope.

## Acceptance criteria
- Duplicated setup/parsing blocks are reduced in touched attestation/proof tests.
- Shared helper extraction preserves existing behavior and deterministic output.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to helper and directly adjacent attestation/proof test surfaces.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- docs/dev/evidence/TASK_265/**

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
- docs/dev/evidence/TASK_265/TESTS.txt
- docs/dev/evidence/TASK_265/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_265/DIFF_STAT.txt
- docs/dev/evidence/TASK_265/HOTFILE_SCAN.txt

## Determinism expectations
- Stable helper behavior and deterministic output on touched tests.
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
