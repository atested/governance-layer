# TASK_271 — Tool-event helper duplication reduction

SPEC_EXPECTED: CODE

## Intent
Reduce duplicated setup/parsing logic across current-main tool-event tests only where shared helper extraction clearly lowers maintenance cost without broadening subsystem scope.

## Acceptance criteria
- Duplicate setup/parsing patterns across touched tool-event export/verify tests are reduced via shared helper logic.
- Helper extraction preserves existing subsystem behavior and explicit error expectations.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing tool-event helper and adjacent test surfaces.

## Files allowed to touch
- system/tests/helpers/**
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_271/**

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
- docs/dev/evidence/TASK_271/TESTS.txt
- docs/dev/evidence/TASK_271/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_271/DIFF_STAT.txt
- docs/dev/evidence/TASK_271/HOTFILE_SCAN.txt

## Determinism expectations
- Shared helper behavior remains deterministic for touched setup/parsing paths.
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
