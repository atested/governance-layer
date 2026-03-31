# TASK_292 — Dev chat startup state wiring

SPEC_EXPECTED: DOC

## Intent
Make BFPS + capability-map startup behavior coherent and minimal so future Dev chats always begin with current planning state, capability-map consultation, and clear reuse-vs-refresh rules.

## Acceptance criteria
- Startup wiring explicitly states: read capability map first for new workfront selection.
- Startup wiring explicitly states: light map update after each Cecil merge; deeper planning refresh only on trigger.
- Capability map includes a compact quick-state section for fast startup reading if needed.
- Process remains compact and operational without broader framework expansion.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_292/**

## Files forbidden to touch
- docs/dev/ASSIGNMENTS.md
- capabilities/capability-registry.json
- mcp/server.py
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- Product/code implementation surfaces.
- Broad doctrine/process docs unrelated to this workfront.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_292/VALIDATION.txt
- docs/dev/evidence/TASK_292/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_292/DIFF_STAT.txt
- docs/dev/evidence/TASK_292/HOTFILE_SCAN.txt

## Determinism expectations
- Startup flow is explicit and repeatable from BFPS + capability-map text only.

## STOP rules
- STOP if startup wiring requires broad process rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No full planning rediscovery in this run unless required for coherence.
