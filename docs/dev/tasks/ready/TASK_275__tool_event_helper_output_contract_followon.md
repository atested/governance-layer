# TASK_275 — Tool-event helper/output contract follow-on

SPEC_EXPECTED: CODE

## Intent
Normalize remaining tool-event helper/output contract inconsistencies on current main across export/verify and adjacent receipt/query-facing output shapes. Standardize stable ordering, ids/digests/reasons, and fail-closed malformed-input behavior where current tool-event helper outputs still differ.

## Acceptance criteria
- Deterministic output structure and stable ordering across touched tool-event surfaces.
- Stable reason/id/digest semantics across touched helper and machine-readable outputs.
- Malformed-input behavior is fail-closed and explicit for touched flows.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged tool-event surfaces and direct tests.

## Files allowed to touch
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/attest/**
- system/tests/**
- docs/dev/evidence/TASK_275/**

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
- docs/dev/evidence/TASK_275/TESTS.txt
- docs/dev/evidence/TASK_275/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_275/DIFF_STAT.txt
- docs/dev/evidence/TASK_275/HOTFILE_SCAN.txt

## Determinism expectations
- Stable helper/output ordering and field-shape behavior for touched tool-event surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server integration beyond listed tool-event files, reporting enrollment, merge work, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if scope drifts outside listed tool-event surfaces.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server integration beyond listed tool-event files.
