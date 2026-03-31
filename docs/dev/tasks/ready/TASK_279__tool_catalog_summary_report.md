# TASK_279 — Tool-catalog summary report

SPEC_EXPECTED: CODE

## Intent
Add a deterministic summary/report artifact for the tool-catalog surface so a bounded catalog state can be inspected without reading raw internal structures. The report is derived from existing catalog data with stable ordering and concise machine-readable output.

## Acceptance criteria
- Deterministic summary/report output for the bounded catalog slice/state.
- Stable ordering and explicit ids/digests/reasons/counts where applicable.
- Report generation remains bounded to existing store/export/report-adjacent behavior.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.

## Files allowed to touch
- mcp/tool_catalog_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_279/**

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
- docs/dev/evidence/TASK_279/TESTS.txt
- docs/dev/evidence/TASK_279/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_279/DIFF_STAT.txt
- docs/dev/evidence/TASK_279/HOTFILE_SCAN.txt

## Determinism expectations
- Report output is deterministic and machine-readable for identical catalog state.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if report behavior cannot remain bounded to existing catalog data.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration.
