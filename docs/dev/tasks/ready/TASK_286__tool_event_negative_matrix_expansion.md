# TASK_286 — Tool-event negative matrix expansion

SPEC_EXPECTED: CODE

## Intent
Add a deeper negative-control matrix for malformed, incompatible, or invalid filtered/report requests on the tool-event surface. The goal is fail-closed behavior and stable extension-safe tests for the new slice/report capability.

## Acceptance criteria
- Negative matrix covers malformed/incompatible/invalid filtered-slice and report requests.
- Failure outputs are deterministic with stable reason-coded status lines.
- Negative-control behavior remains bounded to existing tool-event store/report surfaces.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.

## Files allowed to touch
- mcp/tool_event_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_286/**

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
- Reporting-enrollment surfaces.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_286/TESTS.txt
- docs/dev/evidence/TASK_286/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_286/DIFF_STAT.txt
- docs/dev/evidence/TASK_286/HOTFILE_SCAN.txt

## Determinism expectations
- Negative-control status outputs are deterministic for identical invalid inputs.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if negative matrix cannot remain bounded to existing tool-event store/report surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration.
