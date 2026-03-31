# TASK_293 — BFPS capability-map hard-dependency link

SPEC_EXPECTED: DOC

## Intent
Update BFPS v12 so new Dev briefings must include both the canonical capability-map repo path and canonical GitHub link, and must fail closed if the capability map cannot be read at startup before workfront selection.

## Acceptance criteria
- BFPS requires canonical capability-map path and canonical GitHub link in startup block.
- BFPS requires startup read of capability map before workfront selection.
- BFPS defines hard STOP if capability map is unreadable.
- Changes remain compact and structural.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_293/**

## Files forbidden to touch
- docs/dev/ASSIGNMENTS.md
- capabilities/capability-registry.json
- mcp/server.py
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Product/code implementation surfaces.
- Broad doctrine rewrites.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_293/VALIDATION.txt
- docs/dev/evidence/TASK_293/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_293/DIFF_STAT.txt
- docs/dev/evidence/TASK_293/HOTFILE_SCAN.txt

## Determinism expectations
- BFPS startup rules and STOP condition are explicit and repeatable from file text.

## STOP rules
- STOP if canonical capability-map GitHub link cannot be derived from repo origin cleanly.
- STOP if update requires broad BFPS/doctrine rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
