# TASK_315 — Authoritative workfront source contract

SPEC_EXPECTED: DOC

## Intent
Update capability-map/refresh process contract to define authoritative workfront state clearly and boundedly, alongside capability state, without requiring unbounded planning-file scans.

## Acceptance criteria
- Contract defines two truth classes:
  - capability state
  - authoritative workfront state
- Contract defines authoritative workfront state as including:
  - `docs/dev/WORK_QUEUE.md`
  - current canonical implementation-plan docs for active initiative
  - corresponding ready-task docs for that initiative
- Contract encodes the current required RDD source instance for this bug:
  - `docs/dev/WORK_QUEUE.md`
  - `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
  - `docs/dev/RESIDUAL_DISCRETION_DOCTRINE.md` (with fail-closed resolution if canonical doctrine path differs on main)
  - `docs/dev/tasks/ready/TASK_311__rdd_pass_v02_schema_fields.md`
  - `docs/dev/tasks/ready/TASK_312__rdd_pass_undecided_emission.md`
  - `docs/dev/tasks/ready/TASK_313__rdd_pass_undecided_test_coverage.md`

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_315/**

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
- docs/dev/evidence/TASK_315/VALIDATION.txt
- docs/dev/evidence/TASK_315/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_315/DIFF_STAT.txt
- docs/dev/evidence/TASK_315/HOTFILE_SCAN.txt

## Evidence expectations
- Capability-map/process contract text explicitly encodes authoritative workfront source class and current RDD source instance.

## STOP rules
- STOP if authoritative-source rule cannot be generalized without broad process rewrite.
- STOP if active initiative sources cannot be identified cleanly on main.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No implementation-lane execution in this run.
