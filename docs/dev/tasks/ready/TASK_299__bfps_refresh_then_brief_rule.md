# TASK_299 — BFPS refresh-then-brief rule

SPEC_EXPECTED: DOC

## Intent
Update BFPS v12 so new Dev briefing creation is explicitly a two-stage workflow: refresh canonical capability map first, then generate the briefing from refreshed state only.

## Acceptance criteria
- BFPS explicitly requires canonical map refresh/update before new briefing generation.
- BFPS explicitly forbids briefing generation from in-chat memory, stale prior briefing text, or assistant reconstruction.
- BFPS states that briefing generation occurs only after refresh + merge completion.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_299/**

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
- docs/dev/evidence/TASK_299/VALIDATION.txt
- docs/dev/evidence/TASK_299/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_299/DIFF_STAT.txt
- docs/dev/evidence/TASK_299/HOTFILE_SCAN.txt

## Evidence expectations
- Refresh-then-brief rule and negative prohibitions are explicit and testable in BFPS text.

## STOP rules
- STOP if BFPS change requires broad workflow redesign.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No full planning rediscovery in this run.
