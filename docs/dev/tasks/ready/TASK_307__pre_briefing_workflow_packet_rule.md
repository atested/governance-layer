# TASK_307 — Pre-briefing workflow packet rule

SPEC_EXPECTED: DOC

## Intent
Update the pre-briefing workflow/process so briefing generation after refresh depends on the standardized `BRIEFING EXTRACTION BLOCK` in the refresh completion packet rather than assistant reconstruction.

## Acceptance criteria
- Workflow explicitly states post-refresh briefing generation consumes the standardized extraction block from the completion packet.
- Workflow explicitly states missing or incomplete extraction block is a hard STOP before briefing generation.
- Rule remains bounded to pre-briefing refresh workflow and does not introduce broader process redesign.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_307/**

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
- docs/dev/evidence/TASK_307/VALIDATION.txt
- docs/dev/evidence/TASK_307/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_307/DIFF_STAT.txt
- docs/dev/evidence/TASK_307/HOTFILE_SCAN.txt

## Evidence expectations
- Workflow text provides an explicit fail-closed path for missing extraction block.

## STOP rules
- STOP if packet-based workflow rule cannot be encoded without broader workflow redesign.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
