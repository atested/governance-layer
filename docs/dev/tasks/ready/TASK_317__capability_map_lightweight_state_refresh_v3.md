# TASK_317 — Capability-map lightweight state refresh v3

SPEC_EXPECTED: DOC

## Intent
Refresh the capability map's lightweight current-main state to post-M81 using both canonical capability state and canonical authoritative workfront state on main.

## Acceptance criteria
- Capability map records full current `origin/main` SHA.
- Capability map records latest merge window and latest landed tasks.
- Capability map includes affected/live surface notes for current planning relevance.
- Capability map includes a refresh marker indicating map reflects current main.
- Refresh review includes authoritative workfront sources on main:
  - `docs/dev/WORK_QUEUE.md`
  - `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
  - doctrine path resolution for `docs/dev/RESIDUAL_DISCRETION_DOCTRINE.md` and `docs/RESIDUAL_DISCRETION_DOCTRINE.md`
  - `docs/dev/tasks/ready/TASK_311__rdd_pass_v02_schema_fields.md`
  - `docs/dev/tasks/ready/TASK_312__rdd_pass_undecided_emission.md`
  - `docs/dev/tasks/ready/TASK_313__rdd_pass_undecided_test_coverage.md`

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_317/**

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
- docs/dev/evidence/TASK_317/VALIDATION.txt
- docs/dev/evidence/TASK_317/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_317/DIFF_STAT.txt
- docs/dev/evidence/TASK_317/HOTFILE_SCAN.txt

## Evidence expectations
- Lightweight state fields are current-main grounded and consistent with origin/main and authoritative workfront state on main.

## STOP rules
- STOP if coherent refresh requires broad planning-system rewrite.
- STOP if authoritative workfront state cannot be determined cleanly.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
