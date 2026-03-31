# OPS Canonical Record

This file is the single source of truth for operational workflows, lanes, and invariants.

## Definitions

- Cecil: governance-authorized operator. Sole merger to main. Sole writer of docs/dev/ASSIGNMENTS.md on main at merge time. Primary builder. Receives formal dispatches from Tier 0.
- Tier 0: strategic orchestrator (Claude.ai Max + AutoOn). Produces formal dispatches. Reviews results. Never writes code or executes tasks.
- Cowork: transport tier. Carries dispatches from Tier 0 to Cecil and results from Cecil to Tier 0. Does not make decisions.
- Sonnet-worker: Sonnet-tier subagent within Cecil's session. Handles test verification, merge mechanics, structured validation. Escalates judgment calls to Cecil (Opus).
- Lq, Qt, Bq: supervised collaborators via Ollama. Zero API cost. Output is advisory until Cecil or Sonnet-worker reviews.
- Codex: Codex CLI. Shelved as of ops process v2. Build functions absorbed by Cecil. Test functions absorbed by Sonnet-worker and Qt. May return.
- Primary repo: /Volumes/SSD/archive/gov/governance-layer

## Lanes

### Cecil lane
- Sole merger to main.
- Sole writer of docs/dev/ASSIGNMENTS.md on main at merge time.
- Primary builder. Receives work via formal dispatches from Tier 0.
- Enforces invariants and resolves conflicts per governance rules.
- Manages Sonnet-worker for test verification and merge mechanics.
- Manages sisters (Lq, Qt, Bq) for supervised mechanical work.

### Codex lane [shelved]
- Topic branches only (codex/*).
- Touch only Allowed Files specified by the task.
- Must produce evidence bundles when required by task spec.
- Must push branch to origin. No merges to main.
- Status: Shelved. Scripts retained for potential reactivation.

## Invariants

- Fail closed: if a gate fails, stop and report with evidence.
- Deterministic outputs: no timestamps in generated operational artifacts.
- Allowed Files compliance: task edits must be a subset of task Allowed Files.
- Evidence bundles: when required, include full command output in TESTS.txt.
- Preservation invariant: no agent may delete, overwrite, rename, or move any artifact outside the dispatch's stated scope without explicit permission from Tier 0. Within scope, the agent has full creative latitude. If work within scope requires modifying something outside scope, that is a BLOCKED status — escalate to Tier 0.
- Stage-forward advisory: every results submission must include a stage-forward advisory. When a dispatch includes a Prior advisory, the receiving agent must review it, state what was adopted, and state what was not adopted and why. Ignoring prior advice without explanation is a constraint violation.
- Quality over speed: prefer quality over speed in all work — code, documentation, tests, and evidence.

## Script Registry

- system/scripts/codex-batch.sh
  - Purpose: generate a read-only list of tasks.
  - Lane: Read only. Must not claim tasks or edit WORK_QUEUE.
  - Note: Originally Codex support. Retained for task listing regardless of executor.

- system/scripts/codex-unattended.sh
  - Purpose: unattended gatekeeper runner for preflight, task branch setup, Allowed Files verification, evidence checks, commit, and push.
  - Lane: Codex only [shelved]. Does not merge to main, does not claim tasks, enforces Allowed Files + evidence + push invariants.

- system/scripts/cecil-runloop.sh
  - Purpose: Cecil execution loop. May claim tasks for Cecil.
  - Lane: Cecil only.

- system/scripts/queue-claim.sh
  - Purpose: claim tasks (used by Cecil lane).
  - Lane: Cecil only.

- system/scripts/merge-queue.sh
  - Purpose: automated merging of passing branches.
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
- codex-unattended.sh - Codex gatekeeper runner [shelved]. Contains "git checkout", "git merge", etc. in execution contract documentation block (forbidden commands list). Does not execute these commands; documents them as forbidden. False positive detection.
- inventory-snapshot.sh - Deterministic inventory generator. Contains "checkout main" and "git merge" as grep search patterns only (false positive). Does not execute merge or checkout commands.
- project-status.sh - Read-only status reporter. Switches to main and resets to origin/main for clean state. Generates status report only, no merges, no queue claims.

Deprecated/Disallowed (classified but not approved):
- merge-queue.sh - DEPRECATED. Automated merge behavior violates "Cecil is sole merger to main" invariant. Must not be executed.

## Revision History

- 2026-03-26: Updated for ops process v2 (dispatch architecture). Added Tier 0, Cowork, Sonnet-worker, and sisters to definitions. Codex shelved. Added preservation invariant, stage-forward advisory, and quality-over-speed as system invariants.
- 2026-02-20: Initial canonical ops record created (cecil/OPS-CANONICAL)
