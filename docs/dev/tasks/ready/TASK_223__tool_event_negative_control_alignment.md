# TASK_223 — Tool-event negative-control alignment

SPEC_EXPECTED: CODE

## Intent
Align negative-control behavior and error-shape expectations across current-main tool-event lifecycle and bundle verify/query utilities so malformed-input and mismatch cases are consistently tested and easier to extend.

## Acceptance criteria
- Deterministic failure outputs where applicable on touched surfaces.
- Stable reason-coded negative controls across touched tool-event lifecycle tests/utilities.
- Negative-control tests are self-contained and fail-closed.
- Scope remains bounded to existing merged tool-event lifecycle surfaces and tests.

## Files allowed to touch
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_223/**

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
- docs/dev/evidence/TASK_223/TESTS.txt
- docs/dev/evidence/TASK_223/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_223/DIFF_STAT.txt
- docs/dev/evidence/TASK_223/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic malformed/mismatch failure shapes on touched tool-event surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if alignment requires expansion into unrelated subsystems.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-event files.
