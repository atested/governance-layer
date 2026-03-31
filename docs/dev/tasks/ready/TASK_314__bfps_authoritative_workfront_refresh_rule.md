# TASK_314 — BFPS authoritative workfront refresh rule

SPEC_EXPECTED: DOC

## Intent
Update BFPS v12 so project-state refresh and pre-briefing refresh workflows must inspect both canonical capability state and canonical authoritative workfront state on main.

## Acceptance criteria
- BFPS explicitly requires refresh inputs to include:
  - `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
  - `docs/dev/WORK_QUEUE.md`
  - canonical implementation-plan docs for the active initiative
  - corresponding ready-task docs for that initiative
- BFPS treats the dual-source refresh rule as required, not best effort.
- BFPS allows planning judgment to follow authoritative workfront state when it diverges from recently touched capability seams.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_314/**

## Files forbidden to touch
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
- docs/dev/evidence/TASK_314/VALIDATION.txt
- docs/dev/evidence/TASK_314/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_314/DIFF_STAT.txt
- docs/dev/evidence/TASK_314/HOTFILE_SCAN.txt

## Evidence expectations
- BFPS refresh workflow text clearly encodes mandatory dual-source refresh scope.

## STOP rules
- STOP if required rule cannot be added without broad process redesign.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No implementation-lane execution in this run.
