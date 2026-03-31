# TASK_319 — Capability-map briefing extraction refresh v3

SPEC_EXPECTED: DOC

## Intent
Refresh capability-map fields required for BFPS briefing extraction and require emission of the full standardized `BRIEFING EXTRACTION BLOCK` in this workfront completion packet, aligned to M81 authoritative-workfront refresh scope.

## Acceptance criteria
- Capability-map extraction fields are refreshed for post-M81 current-main state.
- Completion packet includes full standardized `BRIEFING EXTRACTION BLOCK`.
- Extraction block remains sufficient for post-merge briefing generation without assistant reconstruction.
- Completion packet includes authoritative workfront source inclusion details for current required RDD sources.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_319/**

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
- docs/dev/evidence/TASK_319/VALIDATION.txt
- docs/dev/evidence/TASK_319/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_319/DIFF_STAT.txt
- docs/dev/evidence/TASK_319/HOTFILE_SCAN.txt

## Evidence expectations
- Extraction-block readiness is explicit and validated with no briefing generation in this run.

## STOP rules
- STOP if completion packet cannot include a sufficient extraction block.
- STOP if authoritative workfront state cannot be determined cleanly.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No briefing generation in this run.
