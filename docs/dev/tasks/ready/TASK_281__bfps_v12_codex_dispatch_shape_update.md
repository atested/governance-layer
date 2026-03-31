# TASK_281 — BFPS v12 Codex dispatch shape update

SPEC_EXPECTED: DOC

## Intent
Update `BRIEFING_FORMAT__BFPS_v12.md` so it explicitly documents the preferred Codex dispatch shape for qualifying current-main combined workfronts. Keep the addition concise and policy-bounded so BFPS remains briefing authority, not a duplicated dispatch-template repository.

## Acceptance criteria
- BFPS v12 includes a concise, explicit dispatch-shape rule for qualifying current-main combined workfronts.
- The new rule references structural requirements without duplicating large dispatch templates.
- BFPS remains canonical for briefing format and does not broaden into doctrine rewrite.
- Validation is self-contained and does not rely on pre-existing `out/` artifacts unless created by the validation steps.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/evidence/TASK_281/**

## Files forbidden to touch
- docs/dev/ASSIGNMENTS.md
- system/scripts/release-gate.sh
- system/scripts/validate-proof-bundle.sh
- system/scripts/codex-unattended.sh
- capabilities/capability-registry.json
- mcp/server.py
- Any non-doc implementation surface.
- Everything else.

## Required evidence artifacts
- docs/dev/evidence/TASK_281/VALIDATION.txt
- docs/dev/evidence/TASK_281/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_281/DIFF_STAT.txt
- docs/dev/evidence/TASK_281/HOTFILE_SCAN.txt

## Determinism expectations
- BFPS wording is deterministic for equivalent source state.
- Validation outputs are reproducible for the same branch tip.

## STOP rules
- STOP if the update requires changes outside allowed files.
- STOP if the update requires doctrine rewrite beyond this bounded BFPS correction.
- STOP if the update would change hot-file policy itself.

## Constraints
- No merge work.
- No server integration.
- No doctrine rewrite beyond this bounded documentation correction.
- No changes to hot-file policy itself.
