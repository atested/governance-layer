# TASK_288 — Current-main capability map seed

SPEC_EXPECTED: DOC

## Intent
Seed the current-main capability map with concrete post-M73 repo reality so it is immediately usable for bounded next-lane selection without ad hoc rediscovery or chat-memory inference.

## Acceptance criteria
- Map includes current baseline SHA and latest merge window state.
- Map lists active/relevant live surfaces and recent landed work per surface.
- Map avoids broad speculative prose and excludes stale/redundant inventory.
- Seeded content is concrete enough to support bounded next-workfront selection.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_288/**

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
- docs/dev/evidence/TASK_288/VALIDATION.txt
- docs/dev/evidence/TASK_288/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_288/DIFF_STAT.txt
- docs/dev/evidence/TASK_288/HOTFILE_SCAN.txt

## Evidence expectations
- Seed details cite current-main commits/tasks/surfaces visible in repo history and files.

## STOP rules
- STOP if seeding requires speculative architecture judgment outside bounded planning context.
- STOP if forbidden files must be edited.

## Constraints
- No implementation.
- No merge work.
- No doctrine rewrite.
- No stale-branch recovery.
- No server integration.
- No cross-surface architecture changes.
