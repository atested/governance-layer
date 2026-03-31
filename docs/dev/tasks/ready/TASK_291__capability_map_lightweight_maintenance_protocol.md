# TASK_291 — Capability map lightweight maintenance protocol

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` so lightweight post-merge maintenance is explicit and operational, including minimum state fields, judgment-state classifications, and deeper-refresh triggers.

## Acceptance criteria
- Capability map includes explicit lightweight maintenance after every Cecil merge.
- Minimum post-merge update fields are clearly listed: origin/main SHA, latest merge window, landed tasks, affected/live surfaces, planning judgment state.
- Judgment-state set is explicit: `VALID`, `PARTIALLY_CONSUMED`, `EXHAUSTED`, `STALE`, `INSUFFICIENT`.
- Deeper planning refresh triggers are explicit and minimal.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_291/**

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
- docs/dev/evidence/TASK_291/VALIDATION.txt
- docs/dev/evidence/TASK_291/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_291/DIFF_STAT.txt
- docs/dev/evidence/TASK_291/HOTFILE_SCAN.txt

## Determinism expectations
- Maintenance protocol is checklist-style and deterministic to apply per merge window.

## STOP rules
- STOP if protocol update requires creating a second planning artifact.
- STOP if protocol cannot be kept lightweight.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
