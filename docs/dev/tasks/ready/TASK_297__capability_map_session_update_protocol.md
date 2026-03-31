# TASK_297 — Capability-map session update protocol

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` so it explicitly supports extraction into briefing session state and defines in-chat session-state update/continuation rules while the map remains canonical.

## Acceptance criteria
- Capability map explicitly defines extractable session-state subset for BFPS briefings.
- Protocol states: lightweight map update after each Cecil merge; in-chat session-state may be locally updated after merges.
- Protocol states: chat may continue selecting lanes while judgment remains coherent.
- Protocol states: trigger new chat / refreshed map when judgment is `EXHAUSTED`, `STALE`, or `INSUFFICIENT`, or chat quality is flaky enough to reduce trust.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_297/**

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
- docs/dev/evidence/TASK_297/VALIDATION.txt
- docs/dev/evidence/TASK_297/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_297/DIFF_STAT.txt
- docs/dev/evidence/TASK_297/HOTFILE_SCAN.txt

## Determinism expectations
- Session update protocol is operational and checklist-like.

## STOP rules
- STOP if session protocol cannot remain compact and coherent.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No additional planning artifact creation.
