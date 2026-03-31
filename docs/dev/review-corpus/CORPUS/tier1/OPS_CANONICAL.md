# OPS Canonical Record

This file is the single source of truth for operational workflows, lanes, and invariants.

## Definitions

- Cecil: governance-authorized operator. Sole merger to main. Sole writer of docs/dev/ASSIGNMENTS.md on main at merge time.
- Codex: Codex CLI only. Works in topic branches. Never merges to main.
- Primary repo: /Volumes/SSD/archive/gov/governance-layer
- Codex working copy: ~/codex-workspaces/governance-layer

## Lanes

### Codex lane
- Topic branches only (codex/*).
- Touch only Allowed Files specified by the task.
- Must produce evidence bundles when required by task spec.
- Must push branch to origin. No merges to main.

### Cecil lane
- Sole merger to main.
- Sole writer of docs/dev/ASSIGNMENTS.md on main at merge time.
- Enforces invariants and resolves conflicts per governance rules.

## Invariants

- Fail closed: if a gate fails, stop and report with evidence.
- Deterministic outputs: no timestamps in generated operational artifacts.
- Codex batch listing is read only: no queue claiming, no edits to WORK_QUEUE as a side effect.
- Allowed Files compliance: task edits must be a subset of task Allowed Files.
- Evidence bundles: when required, include full command output in TESTS.txt.

## Script Registry

- system/scripts/codex-batch.sh
  - Purpose: generate a read-only list of tasks for Codex.
  - Lane: Codex support (read only). Must not claim tasks or edit WORK_QUEUE.

- system/scripts/codex-unattended.sh
  - Purpose: unattended Codex gatekeeper runner for preflight, task branch setup, Allowed Files verification, evidence checks, commit, and push.
  - Lane: Codex only. Does not merge to main, does not claim tasks, enforces Allowed Files + evidence + push invariants.

- system/scripts/cecil-runloop.sh
  - Purpose: Cecil execution loop. May claim tasks for Cecil.
  - Lane: Cecil only.

- system/scripts/queue-claim.sh
  - Purpose: claim tasks (used by Cecil lane).
  - Lane: Cecil only.

- system/scripts/merge-queue.sh
  - Purpose: automated merging of passing Codex branches.
  - Classification: Deprecated/Disallowed under current invariants unless explicitly re-approved.
  - Reason: violates "Cecil is sole merger to main" and may auto-resolve docs/dev/ASSIGNMENTS.md.

- system/scripts/inventory-snapshot.sh
  - Purpose: deterministic inventory snapshot generator.
  - Lane: Both (read only generator). Must not claim tasks or edit WORK_QUEUE.

## Allowlist for scripts that may merge or touch main

Default: none.
If a script contains merge-to-main behavior, it must be explicitly listed here with rationale and Cecil-only restriction.

Currently approved:
- cecil-runloop.sh - Cecil's execution loop. Authorized to switch to main as Cecil is the sole merger to main. Cecil-only restriction enforced by operational process.
- codex-batch.sh - Read-only batch task lister. Switches to main to read task list from docs/dev/tasks/ready. No writes, no merges, no queue claims.
- codex-unattended.sh - Codex gatekeeper runner. Contains "git checkout", "git merge", etc. in execution contract documentation block (forbidden commands list). Does not execute these commands; documents them as forbidden. False positive detection.
- inventory-snapshot.sh - Deterministic inventory generator. Contains "checkout main" and "git merge" as grep search patterns only (false positive). Does not execute merge or checkout commands.
- project-status.sh - Read-only status reporter. Switches to main and resets to origin/main for clean state. Generates status report only, no merges, no queue claims.

Deprecated/Disallowed (classified but not approved):
- merge-queue.sh - DEPRECATED. Automated merge behavior violates "Cecil is sole merger to main" invariant. Must not be executed.

## Revision History

- 2026-02-20: Initial canonical ops record created (cecil/OPS-CANONICAL)
