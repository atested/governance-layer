# TASK_306 — Capability-map extraction support

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` so the canonical map cleanly supports production of the standardized pre-briefing `BRIEFING EXTRACTION BLOCK` with explicit and stable field mapping.

## Acceptance criteria
- Capability map explicitly defines how extraction-block fields are sourced from canonical map state.
- Mapping is explicit for each required field and does not rely on ad hoc reconstruction.
- Capability map remains compact, canonical, and operational.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_306/**

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
- docs/dev/evidence/TASK_306/VALIDATION.txt
- docs/dev/evidence/TASK_306/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_306/DIFF_STAT.txt
- docs/dev/evidence/TASK_306/HOTFILE_SCAN.txt

## Evidence expectations
- Canonical map text now supports extraction-block generation deterministically and compactly.

## STOP rules
- STOP if extraction support cannot be added without broad planning rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
