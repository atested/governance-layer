# TASK_242 — Tool-catalog negative matrix

SPEC_EXPECTED: CODE

## Intent
Complete malformed-input and mismatch negative-path coverage for current-main tool-catalog query/get/list flows. Keep scope bounded to existing tool-catalog store behavior and tests.

## Acceptance criteria
- Deterministic malformed-input and mismatch behavior across touched tool-catalog query/get/list surfaces.
- Stable reason-coded negative-path expectations where reasons are emitted.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-catalog store behavior and tests.

## Files allowed to touch
- mcp/tool_catalog_store.py
- system/tests/**
- docs/dev/evidence/TASK_242/**

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
- docs/dev/evidence/TASK_242/TESTS.txt
- docs/dev/evidence/TASK_242/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_242/DIFF_STAT.txt
- docs/dev/evidence/TASK_242/HOTFILE_SCAN.txt

## Determinism expectations
- Stable malformed/mismatch output behavior for touched query/get/list paths.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-catalog query/get/list surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

