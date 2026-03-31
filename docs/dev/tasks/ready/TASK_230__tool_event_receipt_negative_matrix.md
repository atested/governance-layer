# TASK_230 — Tool-event receipt negative matrix

SPEC_EXPECTED: CODE

## Intent
Complete malformed-input and mismatch negative-path coverage for receipt-to-tool-event query flows on current main. Keep scope bounded to existing query/link behavior.

## Acceptance criteria
- Deterministic malformed-input and mismatch behavior across touched receipt query surfaces.
- Stable reason-coded negative-path expectations where reasons are emitted.
- Tests are self-contained and do not rely on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing receipt/tool-event query/link behavior.

## Files allowed to touch
- mcp/tool_event_link_store.py
- system/tests/**
- docs/dev/evidence/TASK_230/**

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
- docs/dev/evidence/TASK_230/TESTS.txt
- docs/dev/evidence/TASK_230/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_230/DIFF_STAT.txt
- docs/dev/evidence/TASK_230/HOTFILE_SCAN.txt

## Determinism expectations
- Stable malformed/mismatch output behavior for touched receipt query paths.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed receipt/tool-event query surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
