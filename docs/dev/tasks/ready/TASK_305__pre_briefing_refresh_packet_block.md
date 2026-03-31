# TASK_305 — Pre-briefing refresh packet extraction block

SPEC_EXPECTED: DOC

## Intent
Define the required completion-packet shape for pre-briefing capability-map refresh runs so the packet always includes a standardized `BRIEFING EXTRACTION BLOCK` suitable for direct briefing generation after merge.

## Acceptance criteria
- Pre-briefing refresh completion-packet contract explicitly requires a `BRIEFING EXTRACTION BLOCK`.
- Required extraction block fields are explicit and stable:
  - full current `origin/main` SHA
  - latest merge window
  - latest landed tasks
  - planning judgment state
  - live surfaces summary
  - preferred next lane
  - secondary candidates
  - major constraints / sensitive areas
  - refresh marker indicating map reflects current main
  - current-process state required by BFPS startup
- Contract is compact and directly usable for post-merge briefing generation.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_305/**

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
- docs/dev/evidence/TASK_305/VALIDATION.txt
- docs/dev/evidence/TASK_305/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_305/DIFF_STAT.txt
- docs/dev/evidence/TASK_305/HOTFILE_SCAN.txt

## Evidence expectations
- Required extraction block shape is explicit and can be copied directly into a pre-briefing refresh completion packet.

## STOP rules
- STOP if extraction block sufficiency requires broad workflow redesign.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
