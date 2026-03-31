# TASK_301 — New briefing operator sequence

SPEC_EXPECTED: DOC

## Intent
Encode the explicit operator-facing sequence for new Dev briefing requests: Codex refresh task first, then Cecil merge block, then DEV-number prompt, then final briefing from refreshed canonical map state.

## Acceptance criteria
- BFPS explicitly states required operator sequence for new briefing requests.
- BFPS explicitly states negative rule: do not generate a new briefing immediately upon request.
- Sequence remains lightweight and repeatable.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_301/**

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
- docs/dev/evidence/TASK_301/VALIDATION.txt
- docs/dev/evidence/TASK_301/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_301/DIFF_STAT.txt
- docs/dev/evidence/TASK_301/HOTFILE_SCAN.txt

## Evidence expectations
- Operator sequence and negative rule are explicit and coherent in BFPS flow.

## STOP rules
- STOP if operator sequence cannot be encoded without broad workflow redesign.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
