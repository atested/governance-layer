# TASK_300 — Capability-map briefing extraction contract

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` so briefing-generation extraction fields are explicit and anchored to refreshed canonical state.

## Acceptance criteria
- Capability map explicitly lists the minimum extraction fields required for briefing generation.
- Extraction fields include full origin/main SHA, latest merge window, latest landed tasks, planning judgment state, live surfaces summary, preferred lane, secondary candidates, major constraints/sensitive areas, and refresh marker.
- Capability map remains compact and operational.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_300/**

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
- docs/dev/evidence/TASK_300/VALIDATION.txt
- docs/dev/evidence/TASK_300/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_300/DIFF_STAT.txt
- docs/dev/evidence/TASK_300/HOTFILE_SCAN.txt

## Evidence expectations
- Extraction contract is explicit and directly mappable to BFPS briefing generation.

## STOP rules
- STOP if extraction contract cannot remain compact and explicit.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No full planning rediscovery in this run.
