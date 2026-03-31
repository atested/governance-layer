# TASK_252 — Tool-event receipt/replay negative follow-on

SPEC_EXPECTED: CODE

## Intent
Complete remaining malformed-input, missing-link, and mismatch negative-path coverage for current-main receipt/replay query behavior. Keep scope bounded to existing merged receipt/replay behavior and tests.

## Acceptance criteria
- Deterministic malformed-input, missing-link, and mismatch behavior across touched receipt/replay query surfaces.
- Stable reason/digest/id behavior where present in touched outputs.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event receipt/replay behavior and tests.

## Files allowed to touch
- mcp/tool_event_link_store.py
- system/tests/**
- docs/dev/evidence/TASK_252/**

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
- docs/dev/evidence/TASK_252/TESTS.txt
- docs/dev/evidence/TASK_252/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_252/DIFF_STAT.txt
- docs/dev/evidence/TASK_252/HOTFILE_SCAN.txt

## Determinism expectations
- Stable malformed/missing-link/mismatch behavior for touched receipt/replay surfaces.
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
