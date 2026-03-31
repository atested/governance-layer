# TASK_251 — Tool-event receipt/replay output alignment

SPEC_EXPECTED: CODE

## Intent
Align remaining machine-readable output shapes across current-main receipt/replay query flows where ordering, key presence, or reason/digest formatting still differs. Keep scope bounded to existing merged receipt/replay behavior and tests.

## Acceptance criteria
- Deterministic output structure and stable ordering across touched receipt/replay query surfaces.
- Stable reason/digest/id formatting across touched receipt/replay outputs.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event receipt/replay behavior and tests.

## Files allowed to touch
- mcp/tool_event_link_store.py
- system/tests/**
- docs/dev/evidence/TASK_251/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- mcp/tool_event_store.py
- mcp/tool_catalog_store.py
- scripts/attest/**
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_251/TESTS.txt
- docs/dev/evidence/TASK_251/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_251/DIFF_STAT.txt
- docs/dev/evidence/TASK_251/HOTFILE_SCAN.txt

## Determinism expectations
- Stable output ordering and field-shape behavior for touched receipt/replay surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed receipt/replay surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
