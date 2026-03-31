# TASK_228 — Tool-event replay-check alignment

SPEC_EXPECTED: CODE

## Intent
Align replay-check related tool-event digest/query behavior and expectations across current-main test and utility surfaces. Keep work bounded to current merged tool-event receipt/replay behavior.

## Acceptance criteria
- Deterministic replay-check behavior across touched surfaces.
- Stable reason-coded outputs where failures or mismatch states are emitted.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged tool-event receipt/replay surfaces.

## Files allowed to touch
- mcp/tool_event_link_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_228/**

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
- docs/dev/evidence/TASK_228/TESTS.txt
- docs/dev/evidence/TASK_228/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_228/DIFF_STAT.txt
- docs/dev/evidence/TASK_228/HOTFILE_SCAN.txt

## Determinism expectations
- Stable replay-check reason/digest behavior on touched surfaces.
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
