# TASK_235 — Tool-catalog query test harness extension

SPEC_EXPECTED: CODE

## Intent
Extend shared query/verify fixture helpers or test conventions for tool-catalog edge cases so current-main tests avoid duplicated setup and drift. Improve continuation depth on the same surface without changing subsystem scope.

## Acceptance criteria
- Shared fixture/helper patterns reduce duplicated setup across touched tool-catalog query/verify tests.
- Fixture generation remains deterministic and self-contained.
- No pre-existing `out/` dependency unless created by the test.
- Scope remains bounded to existing merged tool-catalog query/verify surfaces and tests.

## Files allowed to touch
- system/tests/**
- docs/dev/evidence/TASK_235/**

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
- docs/dev/evidence/TASK_235/TESTS.txt
- docs/dev/evidence/TASK_235/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_235/DIFF_STAT.txt
- docs/dev/evidence/TASK_235/HOTFILE_SCAN.txt

## Determinism expectations
- Deterministic fixture generation and normalized output behavior on touched surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if harness changes broaden into unrelated subsystem surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No MCP/server integration beyond listed tool-catalog files.
