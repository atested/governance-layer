# TASK_290 — BFPS v12 capability map required reference

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/BRIEFING_FORMAT__BFPS_v12.md` so every future Dev briefing includes a canonical reference to `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`, its purpose, and mandatory consultation at chat start before selecting a new workfront.

## Acceptance criteria
- BFPS explicitly requires the capability-map path in new Dev briefings.
- BFPS requires capability-map consultation at Dev chat start before new workfront selection.
- BFPS includes concise fields for lightweight map update rule, deeper-refresh trigger, and current judgment summary.
- Changes remain compact and structural.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_290/**

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
- docs/dev/evidence/TASK_290/VALIDATION.txt
- docs/dev/evidence/TASK_290/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_290/DIFF_STAT.txt
- docs/dev/evidence/TASK_290/HOTFILE_SCAN.txt

## Determinism expectations
- BFPS structure requirements are unambiguous and reproducible from source text.

## STOP rules
- STOP if the change requires broad BFPS/doctrine rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
