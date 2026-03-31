# TASK_276 — Tool-event shared fixture refinement

SPEC_EXPECTED: CODE

## Intent
Extend or refine shared deterministic fixture/helper usage on the current-main tool-event test surface so remaining adjacent tests reduce duplication without widening subsystem scope.

## Acceptance criteria
- Shared fixture/helper patterns reduce duplicated setup across touched tool-event tests.
- Fixture generation and helper usage remain deterministic and self-contained.
- Tests do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event test and directly-adjacent helper surfaces.

## Files allowed to touch
- system/tests/**
- scripts/attest/**
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- docs/dev/evidence/TASK_276/**

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
- docs/dev/evidence/TASK_276/TESTS.txt
- docs/dev/evidence/TASK_276/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_276/DIFF_STAT.txt
- docs/dev/evidence/TASK_276/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture behavior on touched tool-event tests.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration beyond listed tool-event files, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if fixture changes broaden into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration beyond listed tool-event files.
