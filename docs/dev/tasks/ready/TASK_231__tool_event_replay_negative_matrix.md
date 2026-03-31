# TASK_231 — Tool-event replay negative matrix

SPEC_EXPECTED: CODE

## Intent
Complete malformed-input and mismatch negative-path coverage for replay-check tool-event digest behavior on current main. Keep scope bounded to existing replay-check behavior.

## Acceptance criteria
- Deterministic malformed-input and mismatch behavior across touched replay-check surfaces.
- Stable reason-coded outputs for negative-path checks where reasons are emitted.
- Tests are self-contained and do not rely on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged replay-check behavior.

## Files allowed to touch
- mcp/tool_event_link_store.py
- system/tests/**
- docs/dev/evidence/TASK_231/**

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
- docs/dev/evidence/TASK_231/TESTS.txt
- docs/dev/evidence/TASK_231/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_231/DIFF_STAT.txt
- docs/dev/evidence/TASK_231/HOTFILE_SCAN.txt

## Determinism expectations
- Stable replay-check negative-path outputs on touched surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed replay-check surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
