# TASK_219 — Attestation shared test harness

SPEC_EXPECTED: CODE

## Intent
Introduce shared fixture/helpers or consistent conventions for attestation/proof utility tests so current-main test setup duplication is reduced and same-surface continuation depth improves.

## Acceptance criteria
- Shared harness/fixtures remove avoidable duplicated setup across targeted tests.
- Fixture generation is deterministic.
- Tests are self-contained and do not require pre-existing `out/` artifacts unless created by the test.
- Scope remains limited to attestation/proof utility tests and adjacent helper files.

## Files allowed to touch
- system/tests/**
- scripts/attest/**
- docs/dev/evidence/TASK_219/**

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
- docs/dev/evidence/TASK_219/TESTS.txt
- docs/dev/evidence/TASK_219/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_219/DIFF_STAT.txt
- docs/dev/evidence/TASK_219/HOTFILE_SCAN.txt

## Determinism expectations
- Shared fixture generation must be deterministic.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if harness generalization drifts outside attestation/proof utility test surfaces.

## Constraints
- No merge work.
- No MCP/server integration.
- No reporting-row onboarding.
- No doctrine changes.
