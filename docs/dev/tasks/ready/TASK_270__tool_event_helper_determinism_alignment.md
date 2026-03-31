# TASK_270 — Tool-event helper determinism alignment

SPEC_EXPECTED: CODE

## Intent
Standardize deterministic helper usage across current-main tool-event export/verify tests where equivalent cases still use divergent setup or hashing patterns. Keep scope bounded to existing merged helper/test behavior.

## Acceptance criteria
- Deterministic helper usage is aligned across touched tool-event export/verify tests.
- Equivalent assertion flows use consistent helper contracts for key/value checks.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event helper/test behavior.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_270/**

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
- docs/dev/evidence/TASK_270/TESTS.txt
- docs/dev/evidence/TASK_270/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_270/DIFF_STAT.txt
- docs/dev/evidence/TASK_270/HOTFILE_SCAN.txt

## Determinism expectations
- Touched helper/setup paths are deterministic across repeated runs.
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
