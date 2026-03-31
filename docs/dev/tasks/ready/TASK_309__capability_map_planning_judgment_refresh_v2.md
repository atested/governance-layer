# TASK_309 — Capability-map planning judgment refresh v2

SPEC_EXPECTED: DOC

## Intent
Refresh bounded planning judgment fields in the capability map based on post-M79 current-main state.

## Acceptance criteria
- Capability map refreshes planning judgment state.
- Capability map refreshes preferred next lane and secondary candidates.
- Capability map refreshes major constraints / sensitive areas with current-main grounding.
- Judgment remains bounded and suitable for immediate briefing extraction.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_309/**

## Files forbidden to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/ASSIGNMENTS.md
- capabilities/capability-registry.json
- mcp/server.py
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Product/code implementation surfaces.
- Broad doctrine rewrites.
- Additional planning artifacts unless directly required and justified.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_309/VALIDATION.txt
- docs/dev/evidence/TASK_309/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_309/DIFF_STAT.txt
- docs/dev/evidence/TASK_309/HOTFILE_SCAN.txt

## Evidence expectations
- Planning judgment is current-main grounded and coherent for next-lane selection.

## STOP rules
- STOP if grounded judgment refresh cannot be produced from current main.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
