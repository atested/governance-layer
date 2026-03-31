# TASK_282 — BFPS v12 dispatch pointer seam resolution

SPEC_EXPECTED: DOC

## Intent
Resolve the BFPS v12 dispatch-library version seam so dispatch pointer wording is explicit, consistent, and minimally drift-prone. Use the narrowest durable correction, and only touch `DISPATCH_LIBRARY__CECIL_CODEX__v10.md` if strictly required by the chosen fix.

## Acceptance criteria
- BFPS pointer language clearly resolves the version seam between canonical and versioned dispatch-library references.
- Pointer language remains internally consistent with the active dispatch-library source of truth.
- Any dispatch-library file edits are omitted unless strictly required for seam resolution.
- Validation is self-contained and does not rely on pre-existing `out/` artifacts unless created by the validation steps.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__v10.md
- docs/dev/evidence/TASK_282/**

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
- docs/dev/evidence/TASK_282/VALIDATION.txt
- docs/dev/evidence/TASK_282/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_282/DIFF_STAT.txt
- docs/dev/evidence/TASK_282/HOTFILE_SCAN.txt

## Determinism expectations
- Version-seam resolution language is deterministic for equivalent source state.
- Validation outputs are reproducible for the same branch tip.

## STOP rules
- STOP if seam resolution requires broad rewrite of BFPS or dispatch-library doctrine.
- STOP if seam resolution requires changes outside allowed files.
- STOP if seam resolution cannot be made explicit without Cecil-level architecture judgment.

## Constraints
- No merge work.
- No server integration.
- No doctrine rewrite beyond this bounded documentation correction.
- No changes to hot-file policy itself.
