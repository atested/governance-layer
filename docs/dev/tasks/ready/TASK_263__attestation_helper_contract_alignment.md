# TASK_263 — Attestation helper contract alignment

SPEC_EXPECTED: CODE

## Intent
Align shared attestation/proof helper outputs and helper-call conventions where current-main tests still use inconsistent parsing or assertion shapes. Keep scope bounded to helper files and directly adjacent tests.

## Acceptance criteria
- Deterministic helper output/usage conventions across touched attestation/proof tests.
- Stable parsing/assertion shape across touched helper callsites.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to helper files and directly adjacent tests.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_263/**

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
- docs/dev/evidence/TASK_263/TESTS.txt
- docs/dev/evidence/TASK_263/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_263/DIFF_STAT.txt
- docs/dev/evidence/TASK_263/HOTFILE_SCAN.txt

## Determinism expectations
- Stable helper output/usage behavior on touched attestation/proof tests.
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
