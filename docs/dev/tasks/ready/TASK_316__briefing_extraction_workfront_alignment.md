# TASK_316 — Briefing extraction workfront alignment

SPEC_EXPECTED: DOC

## Intent
Update refresh/extraction contract so extracted planning state reflects both capability and authoritative workfront inputs, with explicit divergence handling and fail-closed behavior.

## Acceptance criteria
- Refresh/extraction contract explicitly requires both capability-state and authoritative-workfront-state inputs.
- Contract explicitly states that divergence between the two classes must be surfaced, not silently defaulted.
- Contract explicitly requires STOP when authoritative workfront state cannot be determined cleanly.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_316/**

## Files forbidden to touch
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
- docs/dev/evidence/TASK_316/VALIDATION.txt
- docs/dev/evidence/TASK_316/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_316/DIFF_STAT.txt
- docs/dev/evidence/TASK_316/HOTFILE_SCAN.txt

## Evidence expectations
- Refresh/extraction text makes dual-source alignment and fail-closed divergence handling explicit.

## STOP rules
- STOP if extraction alignment cannot be fixed without larger planning-system rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No implementation-lane execution in this run.
