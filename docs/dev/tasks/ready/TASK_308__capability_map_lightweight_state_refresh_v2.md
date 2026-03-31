# TASK_308 — Capability-map lightweight state refresh v2

SPEC_EXPECTED: DOC

## Intent
Refresh the capability map's lightweight current-main state to post-M79 so briefing extraction uses current canonical values.

## Acceptance criteria
- Capability map records full current `origin/main` SHA.
- Capability map records latest merge window and latest landed tasks.
- Capability map includes affected/live surface notes for current planning relevance.
- Capability map includes a refresh marker indicating map reflects current main.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_308/**

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
- docs/dev/evidence/TASK_308/VALIDATION.txt
- docs/dev/evidence/TASK_308/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_308/DIFF_STAT.txt
- docs/dev/evidence/TASK_308/HOTFILE_SCAN.txt

## Evidence expectations
- Lightweight state fields are current-main grounded and consistent with origin/main.

## STOP rules
- STOP if coherent refresh requires broad planning-system rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
