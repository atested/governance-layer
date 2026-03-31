# TASK_289 — Current-main capability map protocol

SPEC_EXPECTED: DOC

## Intent
Define a lightweight update/read protocol for the current-main capability map so the artifact stays current with normal merge flow and is consulted before new workfront selection.

## Acceptance criteria
- Protocol specifies post-merge update cadence and minimum update fields.
- Protocol defines triggers for deeper planning refresh.
- Protocol defines when Dev chat + Greg should read the map before dispatching new workfronts.
- Protocol includes explicit planning judgment state classification (e.g., VALID / PARTIALLY_CONSUMED / EXHAUSTED / STALE / INSUFFICIENT).
- Protocol stays minimal and operational.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_289/**

## Files forbidden to touch
- docs/dev/ASSIGNMENTS.md
- capabilities/capability-registry.json
- mcp/server.py
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Product/code implementation surfaces.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_289/VALIDATION.txt
- docs/dev/evidence/TASK_289/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_289/DIFF_STAT.txt
- docs/dev/evidence/TASK_289/HOTFILE_SCAN.txt

## Evidence expectations
- Protocol is testable by simple checklist validation and remains lightweight.

## STOP rules
- STOP if protocol requires broad doctrine/process rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No implementation.
- No merge work.
- No doctrine rewrite.
- No stale-branch recovery.
- No server integration.
- No cross-surface architecture changes.
- No second planning artifact unless directly required and justified.
