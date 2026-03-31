# TASK_277 — Tool-event negative-control follow-on

SPEC_EXPECTED: CODE

## Intent
Align remaining malformed-input, mismatch, and fail-closed negative-control cases across the current-main tool-event export/verify/query-adjacent surface.

## Acceptance criteria
- Deterministic failure outputs where applicable for malformed-input and mismatch controls.
- Stable reason-coded negative controls across touched tool-event surfaces.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged tool-event surfaces and tests.

## Files allowed to touch
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_277/**

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
- docs/dev/evidence/TASK_277/TESTS.txt
- docs/dev/evidence/TASK_277/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_277/DIFF_STAT.txt
- docs/dev/evidence/TASK_277/HOTFILE_SCAN.txt

## Determinism expectations
- Stable reason-coded negative-control behavior and error shapes across touched surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration beyond listed tool-event files, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-event surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration beyond listed tool-event files.
