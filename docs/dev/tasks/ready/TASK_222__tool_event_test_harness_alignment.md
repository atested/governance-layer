# TASK_222 — Tool-event test harness alignment

SPEC_EXPECTED: CODE

## Intent
Introduce shared test fixture/helpers or consistent conventions for current-main tool-event lifecycle tests to reduce duplicated setup logic while preserving subsystem scope.

## Acceptance criteria
- Shared harness/fixtures reduce avoidable setup duplication across targeted tool-event tests.
- Fixture generation is deterministic.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains limited to tool-event lifecycle and adjacent attest utility test surfaces.

## Files allowed to touch
- system/tests/**
- scripts/attest/**
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- docs/dev/evidence/TASK_222/**

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
- docs/dev/evidence/TASK_222/TESTS.txt
- docs/dev/evidence/TASK_222/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_222/DIFF_STAT.txt
- docs/dev/evidence/TASK_222/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture generation and deterministic test outputs where applicable.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if harness changes broaden into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-event files.
