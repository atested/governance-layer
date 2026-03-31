# TASK_250 — Attestation verify fixture alignment

SPEC_EXPECTED: CODE

## Intent
Extend shared verify-side fixture/helpers or conventions only as needed to support the completed negative-path matrix without duplicated setup.

## Acceptance criteria
- Shared fixture/helper patterns reduce duplicated setup across touched verify-side tests.
- Fixture generation remains deterministic and self-contained.
- No pre-existing `out/` dependency unless created by the test.
- Scope remains bounded to existing attestation/proof verify-side surfaces and tests.

## Files allowed to touch
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_250/**

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
- docs/dev/evidence/TASK_250/TESTS.txt
- docs/dev/evidence/TASK_250/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_250/DIFF_STAT.txt
- docs/dev/evidence/TASK_250/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture generation on touched verify-side tests.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if fixture changes broaden into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
