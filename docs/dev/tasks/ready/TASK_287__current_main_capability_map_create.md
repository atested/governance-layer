# TASK_287 — Current-main capability map create

SPEC_EXPECTED: DOC

## Intent
Create a minimal, stable-path current-main capability map at `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` for decision support during next-workfront selection. This artifact is operational and compact, not a full architecture catalog.

## Acceptance criteria
- `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` exists and is structured for planning use.
- Map includes the required bounded sections: baseline, latest merge window, latest landed tasks, live surfaces, recent landed work, adjacent bounded seams, constraints/risk notes, leverage judgment, current planning judgment, and staleness/exhaustion note.
- Content is concise and decision-oriented.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_287/**

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
- docs/dev/evidence/TASK_287/VALIDATION.txt
- docs/dev/evidence/TASK_287/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_287/DIFF_STAT.txt
- docs/dev/evidence/TASK_287/HOTFILE_SCAN.txt

## Evidence expectations
- Map is seeded from origin-backed current-main facts available at execution time.

## STOP rules
- STOP if creating the map requires broad repo-wide inventorying beyond bounded planning utility.
- STOP if forbidden files must be edited.

## Constraints
- No implementation.
- No merge work.
- No doctrine rewrite.
- No stale-branch recovery.
- No server integration.
- No cross-surface architecture changes.
