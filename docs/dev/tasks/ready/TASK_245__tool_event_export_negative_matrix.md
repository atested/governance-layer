# TASK_245 — Tool-event export negative matrix

SPEC_EXPECTED: CODE

## Intent
Complete malformed-input and mismatch negative-path coverage for current-main tool-event bundle export behavior. Keep scope bounded to existing merged export behavior and tests.

## Acceptance criteria
- Deterministic malformed-input and mismatch behavior across touched export surfaces.
- Stable reason-coded negative-path expectations where reasons are emitted.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event export behavior and tests.

## Files allowed to touch
- scripts/attest/export_tool_event_bundle.py
- system/tests/**
- docs/dev/evidence/TASK_245/**

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
- docs/dev/evidence/TASK_245/TESTS.txt
- docs/dev/evidence/TASK_245/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_245/DIFF_STAT.txt
- docs/dev/evidence/TASK_245/HOTFILE_SCAN.txt

## Determinism expectations
- Stable malformed/mismatch output behavior for touched export paths.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-event export surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
