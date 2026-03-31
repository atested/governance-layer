# TASK_237 — Tool-event verify contract alignment

SPEC_EXPECTED: CODE

## Intent
Align verify output and error-shape behavior for current-main tool-event bundle verification. Keep work bounded to existing merged verify behavior and tests.

## Acceptance criteria
- Deterministic verify behavior across touched verification surfaces.
- Stable reason-coded outputs where failures or mismatch states are emitted.
- Negative controls for malformed inputs are explicit and fail-closed.
- Tests are self-contained and do not depend on pre-existing `out/` artifacts unless created by the test.
- Scope remains bounded to existing merged tool-event verify behavior and tests.

## Files allowed to touch
- scripts/attest/verify_tool_event_bundle.py
- system/tests/**
- docs/dev/evidence/TASK_237/**

## Files forbidden to touch
- capabilities/capability-registry.json
- mcp/server.py
- mcp/tool_event_store.py
- mcp/tool_event_link_store.py
- scripts/dev_phase2_regression.sh
- scripts/dev_generate_verification_catalog.py
- system/planning/verification_catalog.v1.json
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_237/TESTS.txt
- docs/dev/evidence/TASK_237/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_237/DIFF_STAT.txt
- docs/dev/evidence/TASK_237/HOTFILE_SCAN.txt

## Determinism expectations
- Stable verify reason/digest behavior on touched verification surfaces.
- run1/run2 normalized output SHA256 must match where applicable.

## STOP rules
- STOP if implementation requires server wiring, reporting enrollment, or doctrine changes.
- STOP if implementation requires hot-file edits.
- STOP if alignment requires expansion into unrelated subsystems.

## Constraints
- No merge work.
- No reporting enrollment.
- No doctrine changes.
- No server wiring.

