# TASK_298 — Dev number prompt in briefing creation

SPEC_EXPECTED: DOC

## Intent
Update BFPS/new-chat startup process so briefing creation explicitly prompts Greg for the DEV number while proposing the next expected value (for example: “Ready to create the briefing using DEV11?”).

## Acceptance criteria
- BFPS explicitly requires a pre-briefing DEV-number prompt step.
- Rule supports both confirmation (`yes`) and explicit override by Greg.
- Startup sequence remains compact and does not expand into broader workflow redesign.

## Files allowed to touch
- docs/dev/BRIEFING_FORMAT__BFPS_v12.md
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_298/**

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
- docs/dev/evidence/TASK_298/VALIDATION.txt
- docs/dev/evidence/TASK_298/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_298/DIFF_STAT.txt
- docs/dev/evidence/TASK_298/HOTFILE_SCAN.txt

## Determinism expectations
- Prompt rule is explicit, minimal, and deterministic in BFPS startup protocol.

## STOP rules
- STOP if DEV prompt integration requires broad BFPS rewrite.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
