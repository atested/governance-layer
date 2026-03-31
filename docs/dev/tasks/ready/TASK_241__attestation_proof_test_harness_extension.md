# TASK_241 — Attestation/proof test harness extension

SPEC_EXPECTED: CODE

## Intent
Extend shared test fixture/helpers or conventions for attestation/proof utilities only where needed to reduce duplicated setup and drift across current-main tests. Improve continuation depth on the same surface without changing subsystem scope.

## Acceptance criteria
- Shared fixture/helper patterns reduce duplicated setup across touched attestation/proof tests.
- Fixture generation remains deterministic and self-contained.
- No pre-existing `out/` dependency unless created by the test.
- Scope remains bounded to existing merged attestation/proof utilities and tests.

## Files allowed to touch
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_241/**

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
- docs/dev/evidence/TASK_241/TESTS.txt
- docs/dev/evidence/TASK_241/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_241/DIFF_STAT.txt
- docs/dev/evidence/TASK_241/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture generation on touched attestation/proof tests.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if harness changes broaden into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

