# TASK_232 — Tool-event receipt fixture alignment

SPEC_EXPECTED: CODE

## Intent
Extend shared receipt/replay fixture helpers only as needed to support the completed negative-path matrix without duplicated setup.

## Acceptance criteria
- Shared fixture/helper patterns reduce duplicated setup across touched receipt/replay negative-path tests.
- Fixture generation remains deterministic and self-contained.
- No pre-existing `out/` dependency unless created by the test.
- Scope remains bounded to existing tool-event receipt/replay query tests.

## Files allowed to touch
- system/tests/**
- docs/dev/evidence/TASK_232/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- mcp/tool_event_store.py
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_232/TESTS.txt
- docs/dev/evidence/TASK_232/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_232/DIFF_STAT.txt
- docs/dev/evidence/TASK_232/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture generation and normalized test outputs on touched surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if fixture alignment broadens into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
