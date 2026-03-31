# TASK_295 — Dev chat numbering and startup wiring

SPEC_EXPECTED: DOC

## Intent
Make BFPS startup identity and sequencing explicit as `DEV<N>` and wire startup flow so capability-map read (with fail-closed behavior) occurs before planning/workfront selection.

## Acceptance criteria
- BFPS header identity explicitly uses `DEV<N>` naming.
- BFPS startup flow clearly orders: DEV<N> identity -> capability-map read -> fail-closed if unreadable -> planning/workfront selection.
- Wiring remains minimal and bounded.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_295/**

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
- docs/dev/evidence/TASK_295/VALIDATION.txt
- docs/dev/evidence/TASK_295/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_295/DIFF_STAT.txt
- docs/dev/evidence/TASK_295/HOTFILE_SCAN.txt

## Determinism expectations
- Startup sequence and identity format are explicit and reproducible from BFPS text.

## STOP rules
- STOP if numbering/startup updates require a broad BFPS rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
- No duplicated planning-state block unless directly required.
