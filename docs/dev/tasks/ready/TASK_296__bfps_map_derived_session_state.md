# TASK_296 — BFPS map-derived session state

SPEC_EXPECTED: DOC

## Intent
Update BFPS v12 so new Dev briefings must include a required Current Planning State section derived from `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`, sufficient for repeated planning use during the life of a chat.

## Acceptance criteria
- BFPS explicitly requires a `Current Planning State` section derived from the capability map.
- Required content shape includes: baseline, latest merge window, latest landed tasks, planning judgment state, live surfaces summary, preferred next lane, secondary candidates, major constraints/sensitive areas, and refresh/new-chat trigger note.
- BFPS keeps this section as extracted subset, not duplicated full map content.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_296/**

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
- docs/dev/evidence/TASK_296/VALIDATION.txt
- docs/dev/evidence/TASK_296/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_296/DIFF_STAT.txt
- docs/dev/evidence/TASK_296/HOTFILE_SCAN.txt

## Determinism expectations
- Current Planning State requirements are explicit and repeatable from BFPS text.

## STOP rules
- STOP if BFPS update requires broad process rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No duplicated full map content in BFPS.
