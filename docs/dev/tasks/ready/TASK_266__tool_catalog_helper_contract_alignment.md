# TASK_266 — Tool-catalog helper contract alignment

SPEC_EXPECTED: CODE

## Intent
Align shared tool-catalog helper outputs and helper-call conventions where current-main tests still use inconsistent parsing or assertion shapes. Keep scope bounded to helper files and directly adjacent tests.

## Acceptance criteria
- Stable helper output/assertion conventions are used across touched tool-catalog export/verify tests.
- Machine-readable export/verify line assertions are normalized to shared helper patterns.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to tool-catalog helper and directly adjacent test/output surfaces.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_266/**

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
- docs/dev/evidence/TASK_266/TESTS.txt
- docs/dev/evidence/TASK_266/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_266/DIFF_STAT.txt
- docs/dev/evidence/TASK_266/HOTFILE_SCAN.txt

## Determinism expectations
- Shared helper assertions produce stable parse outcomes for touched export/verify outputs.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires edits outside the bounded helper/output surface.
- STOP if implementation requires hot-file edits.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.
