# TASK_280 — Tool-catalog negative matrix expansion

SPEC_EXPECTED: CODE

## Intent
Add a deeper negative-control matrix for malformed, incompatible, or invalid filtered/report requests on the tool-catalog surface so the new slice/report behavior fails closed and remains testable under extension.

## Acceptance criteria
- Deterministic fail-closed behavior for malformed/incompatible filtered/report requests.
- Stable reason-coded negative outputs for touched tool-catalog slice/report flows.
- Negative-control coverage is explicit and extends existing matrix depth on the same surface.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.

## Files allowed to touch
- mcp/tool_catalog_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_280/**

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
- docs/dev/evidence/TASK_280/TESTS.txt
- docs/dev/evidence/TASK_280/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_280/DIFF_STAT.txt
- docs/dev/evidence/TASK_280/HOTFILE_SCAN.txt

## Determinism expectations
- Negative-control outputs remain stable for identical malformed/incompatible inputs.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if negative-control behavior cannot remain bounded to existing tool-catalog data and tests.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration.
