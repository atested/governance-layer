# TASK_294 — Capability-map canonical link integration

SPEC_EXPECTED: DOC

## Intent
Update `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md` to carry a coherent canonical GitHub link reference that matches BFPS and supports hard-dependency startup use.

## Acceptance criteria
- Capability map includes canonical GitHub link to itself.
- Capability map and BFPS reference the same canonical link and path.
- Capability map remains compact and operational.

## Files allowed to touch
- docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md
- docs/dev/evidence/TASK_294/**

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
- docs/dev/evidence/TASK_294/VALIDATION.txt
- docs/dev/evidence/TASK_294/DIFF_NAME_ONLY.txt
- docs/dev/evidence/TASK_294/DIFF_STAT.txt
- docs/dev/evidence/TASK_294/HOTFILE_SCAN.txt

## Determinism expectations
- Canonical link and quick-state references are deterministic and not branch-local placeholders.

## STOP rules
- STOP if canonical link cannot be derived from repo origin configuration.
- STOP if forbidden files must be edited.

## Constraints
- No merge work.
- No server integration.
- No reporting enrollment.
- No stale-branch recovery.
- No cross-surface architecture changes.
