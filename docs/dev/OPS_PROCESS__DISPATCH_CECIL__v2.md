# Ops Process: Dispatch Architecture

Version: v2
Scope: Multi-project development operations, task throughput, merge hygiene, and strategic coherence.
Supersedes: OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md (preserved as historical reference).

## 1. Purpose

This document defines how Greg, Tier 0, Cowork, Cecil, Sonnet-worker, and the sisters (Lq, Qt, Bq) collaborate across all projects under this development architecture.

It is designed to be durable across sessions. Any session participating in a governed project must follow this process unless Greg explicitly overrides it.

This process is **project-agnostic**. Project-specific configuration (repo paths, active task queues, capability surfaces) lives in project-level documents, not here.

## 2. Roles and relationships

### 2.1 Greg (human product owner and source of intent)

Greg is the source of intent, priorities, and acceptance decisions.

Greg does not perform implementation or terminal work.

Greg generally does not:
1. Run terminal commands.
2. Edit files manually.
3. Insert preambles or glue steps.
4. Move files around or resolve merge conflicts by hand.

If any of those actions are required, the system must delegate them to Cecil via explicit dispatch.

Greg does:
1. Provide goals, constraints, and acceptance intent.
2. Work with Tier 0 for planning, design, and spec work — typically once or twice daily, at home or via screen sharing.
3. Decide when to spend Cecil capacity versus defer work.
4. Declare when a merge window is authorized.
5. Deliver dispatches to Cecil and results back to Tier 0 (via Cowork or paste).

Ideally, enough work is prepped that Greg does not need to actively keep things moving between sessions.

### 2.2 Tier 0 (Claude.ai Max + AutoOn — strategic orchestrator)

Tier 0 is the strategic orchestrator. It never writes code or executes tasks.

Tier 0 responsibilities:
1. Plan work with Greg and produce formal dispatches.
2. Review results against acceptance criteria.
3. Approve or reject merges based on results.
4. Surface progress, failures, and blockers at session start.
5. Triage failures — failures always go to front of line.
6. Manage multiple concurrent project workstreams through the same dispatch protocol.
7. Keep the system honest about constraints, allowlists, and stop rules.
8. Preserve continuity across sessions and prevent drift in procedures.

Tier 0 must not create "extra tasks" implicitly. Any new work must be:
1. Proposed explicitly in a dispatch, or
2. Requested explicitly by Greg.

### 2.3 Cowork + Dispatch (transport tier)

Cowork is the transport layer between Tier 0 and Cecil. It does not think or make decisions — it carries.

Cowork responsibilities:
1. Pick up results from Cecil's output and deliver them to Tier 0.
2. Fetch files from the repo on Tier 0's behalf.
3. Deliver dispatches from Tier 0 to Cecil.

Configuration: Cowork Project pointed at the active project repo.

### 2.4 Cecil (strategic lead, sole merger to main, builder)

Cecil is the primary builder, strategic lead, and governance steward.

Cecil responsibilities span four areas:
1. **Build execution.** Receive formal dispatches via Cowork or Greg. Execute build tasks. Report results in formal Results format.
2. **Strategic direction and project coherence.** Architecture and invariants. Philosophy and governance principles. Priority shaping when tradeoffs appear.
3. **High-stakes operational work.** Merge windows to main. Conflict resolution under documented rules. Repo-wide hygiene when changes cross boundaries.
4. **Review and arbitration.** When outputs conflict with architecture. When evidence or determinism claims look suspicious. When a change impacts governance semantics.

Cecil is the sole merger to `main` and the sole writer of `docs/dev/ASSIGNMENTS.md` on `main` at merge time, following the project's merge policy.

Cecil manages test verification through Sonnet-worker and mechanical work through the sisters, within his tasks.

### 2.5 Sonnet-worker (test verification subagent within Cecil)

Sonnet-worker operates within Cecil's session as a subordinate agent at Sonnet tier. It is not a separate agent — it runs as a subagent spawned by Cecil.

Sonnet-worker handles:
1. Test execution and verification.
2. Merge mechanics (checkout, merge, push) per the Sonnet-first execution model (see §7.5).
3. Routine conflict handling within established policy (e.g., ASSIGNMENTS.md union rule).
4. Merge report drafting.
5. Structured validation and consistency checks.

Sonnet-worker escalates to Cecil (Opus) per the escalation conditions in §7.5.4.

### 2.6 The Sisters — Lq, Qt, Bq (supervised collaborators via Ollama)

The sisters are local models running via Ollama at zero API cost. They are supervised collaborators — they contribute observations, flag issues, and surface advice within their capabilities, but Cecil or Sonnet-worker always reviews their output.

**Lq (Little Queen)**:
- Model: `qwen2.5:7b-instruct`
- Role: Classification, tagging, preprocessing, and drafting.
- Typical tasks: Document classification, metadata extraction, draft generation for Cecil's review.

**Qt (Queen of Tests)**:
- Model: `qwen2.5:7b-instruct`
- Role: QA-specific mechanical work and adversarial auditing.
- Typical tasks: Test plan generation, evidence packet validation, structured QA jobs.
- Constraints: May write only to `qa/test-plans/` and `qa/evidence/`. No code edits. Fail closed on invalid requests.

**Bq (Big Queen)**:
- Model: Larger context window model (configurable).
- Role: Tasks requiring extended context that exceed 7b model capabilities.
- Typical tasks: Long-document analysis, cross-file consistency checks.

All sisters operate under Cecil's supervision. Their output is advisory until reviewed and accepted by Cecil or Sonnet-worker.

### 2.7 Codex (shelved)

Codex CLI is shelved as of v2. It may return in future.

Its build functions are absorbed by Cecil. Its test functions are absorbed by Sonnet-worker and Qt. References in operational procedures are preserved with "[shelved]" annotations for continuity.

## 3. Core collaboration loop

### 3.1 The dispatch/results cycle

1. Greg and Tier 0 plan work and produce dispatches. Evening planning sessions can produce gated sequences for overnight execution.
2. Dispatches are delivered to Cecil via Cowork or Greg paste.
3. Cecil executes, delegating to Sonnet-worker for testing and verification, and to sisters for mechanical work within Cecil's tasks.
4. Cecil writes complete results (including subtask results) to a known output path.
5. Cowork picks up results and delivers to Tier 0, or Greg uploads.
6. Tier 0 reviews results, triages failures (failures always go to front of line), and produces next dispatch.

### 3.2 Gated sequences

Tier 0 may produce a sequence of dispatches with explicit gate conditions between them. Cecil works through the sequence autonomously. Rules:

1. Each gate requires its acceptance criteria to be met before the next dispatch activates.
2. If anything fails, the sequence stops and waits for Tier 0 review.
3. Gate conditions must be testable by Cecil or Sonnet-worker — no subjective judgment gates.
4. This enables overnight autonomous work within quality constraints.

### 3.3 What counts as "progress"

Progress is not "more branches." Progress is:
1. Landed changes on `origin/main`, or
2. Published branches that are intentionally staged and reduce future merge cost, or
3. Evidence and contract hardening that makes future work safer, or
4. Strategic clarity that prevents wasted build cycles.

## 4. Task creation rules

### 4.1 No spec, no task

Cecil may not implement a TASK unless its spec exists on the branch tip that Cecil is working from.

If a spec is missing:
1. Cecil stops and reports BLOCKED.
2. Tier 0 issues a SPEC dispatch to create the spec.
3. Only after the spec is landed or the task branch is based on the spec tip may Cecil implement.

### 4.2 Restock branches are first-class work

When new work is needed, Tier 0 should prefer:
1. A restock dispatch that adds task specs and WORK_QUEUE entries, then
2. Per-task implementation dispatches based on the restock tip, or
3. A bundle dispatch only when it materially reduces merge count and does not increase conflict risk.

### 4.3 Encourage full capability within constraints

Each TASK spec should be written to allow meaningful contribution:
1. Clear intent and acceptance conditions.
2. Tight allowlists to keep blast radius small.
3. Sufficient freedom for Cecil to choose the best structure, tests, and determinism strategy.
4. Explicit STOP rules that prevent guessing or scope creep.

The goal is not micromanagement. The goal is bounded autonomy.

## 5. Hot files and conflict control

### 5.1 Hot file list

These files are high merge contention and must be treated as hot:
1. `system/scripts/release-gate.sh`
2. `system/scripts/validate-proof-bundle.sh`
3. `docs/dev/WORK_QUEUE.md`
4. `docs/dev/ASSIGNMENTS.md` (main only, Cecil at merge time)

### 5.2 Hot file handling

Default behavior:
1. Prefer tests-only and docs-only work when not in a merge window.
2. Do not touch hot files unless the dispatch scope explicitly includes them.
3. Batch tasks to minimize repeated touches to the same hot file.

When hot file edits are required:
1. Prefer bundling related hot file changes into one merge unit to reduce cumulative conflicts.
2. Cecil manages hot file merges directly when the conflict risk is nontrivial.

## 6. Evidence and determinism contract

Every CODE task must produce:
1. `docs/dev/evidence/TASK_###/TESTS.txt`
2. Two-run determinism proof where applicable:
   1. run1 hash
   2. run2 hash
   3. assertion that they match
3. Stable negative control markers when failure is expected.

If output contains nondeterministic data (timestamps, temp paths):
1. Normalize in the test harness before hashing.
2. The normalization must itself be deterministic and documented.

### 6.1 Validation scope expansion by touched sensitive surface

Validation scope is not task-local by default when a branch touches sensitive validation surfaces with adjacent invariant gates.

Rule:
1. If a branch touches any signing / record-emission surface, validation scope MUST expand to required adjacent gates.
2. Missing required adjacent gate coverage is STOP (fail-closed), not a soft omission.
3. Dispatches and results must declare touched sensitive surfaces and required adjacent gates explicitly.

Initial sensitive surface family (proven case only):
1. `scripts/policy-eval.py`
2. `scripts/verify-record.py`
3. signing preimage logic
4. record hash construction
5. signed emission field selection

Required adjacent gates for this family:
1. `tests/test_signing_emit.sh`
2. `tests/test_signing_determinism.sh`

Scope constraint:
1. This rule currently codifies only the proven signing/record-emission family above.
2. Do not infer a broad taxonomy without an explicit follow-on process update.

## 7. Merge strategy and Cecil budget usage

### 7.1 Merge window sizes

**M0: No merge.**
Used when Cecil can continue producing low-conflict branches without being blocked.

**M1: Minimal unblock merge.**
Merge only what unblocks work or prevents accumulating dangerous divergence.

**M2: Medium merge.**
Merge a coherent tranche that reduces future merge pressure without exploding conflict risk.

**M3: Large merge.**
Merge multiple related branches including hot file changes to reset the baseline and restore high throughput.

### 7.2 When to trigger a merge window

A merge window is justified when at least one is true:
1. Cecil is blocked because required specs or dependencies are only on branch tips.
2. Unmerged hot file changes are stacking and increasing future conflict cost.
3. The repo baseline is drifting such that outputs keep requiring recuts.
4. There is a backlog of high-value bundles whose merge will reduce merge count materially.

If none are true, do not merge. Keep building on non-merge tasks.

### 7.3 Cecil capacity policy

Policy:
1. Prefer generating mergeable bundles and clean branches.
2. Use Cecil for:
   1. Merges to main.
   2. Conflict resolution.
   3. Architecture-critical decisions and philosophical direction.
   4. Repo-wide corrections that require judgment.
3. Delegate mechanical work to Sonnet-worker and the sisters.

### 7.4 Merge completion control-plane sync check

Before a Cecil merge is considered complete, Cecil must determine whether the merge changed control-plane truth.

Minimum control-plane sync questions:
1. Did this merge land a new capability or governed surface?
2. Did this merge materially consume a previously live tranche or family?
3. Did this merge invalidate or materially weaken the current next-workfront recommendation?
4. Did this merge make an existing family label or canonical planning statement stale or misleading?

Disposition rule:
1. If all answers are `NO`, no canon sync is required.
2. If any answer is `YES`, Cecil must do one of the following before closing the merge:
   1. Update the minimal canonical planning/status surfaces now, if the sync is narrow and unambiguous.
   2. Create or require an immediate bounded follow-on sync task, if the sync requires broader synthesis.

Default preference:
1. Prefer updating canon during merge completion when the required sync is narrow and unambiguous.
2. Use an immediate follow-on sync task only when the sync requires broader synthesis.

Scope boundary:
1. This is a lightweight merge responsibility, not a standing obligation to run a broad audit on every merge.
2. The merge owner only needs to make an explicit control-plane disposition instead of letting canon drift implicitly.

### 7.5 Cecil merge execution model: Sonnet-first, Opus-verify

Cecil merge operations use a two-tier execution model. Sonnet-worker is the default merge executor. Cecil (Opus) is the supervisory verifier and exception authority.

#### 7.5.1 Default merge path

Routine merge execution defaults to Sonnet-worker. Opus does not default to executing routine merge mechanics directly.

#### 7.5.2 Sonnet-worker-owned merge functions

Sonnet-worker handles:
1. Routine merge execution (checkout, merge, push).
2. Standard merge mechanics (branch verification, diff stat, conflict detection).
3. Straightforward conflict handling within established policy and pattern (e.g., ASSIGNMENTS.md union rule).
4. Merge report drafting (landed files, conflict status, diff stat).
5. Standard merge-owned follow-through that is already governed and not judgment-heavy.

#### 7.5.3 Opus-owned merge functions

Opus retains exclusive authority over:
1. Final merge acceptance or rejection.
2. Semantic conflict judgment when ambiguity exists (competing intent, unclear resolution).
3. Architectural arbitration (when merge result affects system structure).
4. Policy-boundary decisions (when merge touches governance rules or invariants).
5. Failover execution when Sonnet-worker is inadequate (see §7.5.5).

#### 7.5.4 Escalation conditions

Sonnet-worker must escalate to Opus when:
1. Semantic conflict requires meaning-level judgment (not just textual resolution).
2. Architectural choice is implicated by the merge result.
3. Policy boundary is touched (governance rules, invariants, merge gate rules).
4. Merge result is uncertain or not cleanly verifiable by Sonnet-worker.
5. Conflict resolution would require interpreting competing intent rather than applying an established rule.

If none of these conditions are met, Sonnet-worker proceeds with routine execution and reports to Opus for verification.

#### 7.5.5 Verification rule

Opus verifies Sonnet-worker's merge result before final acceptance. Verification includes:
1. Confirming the merge topology is correct (parents, branch, no unexpected files).
2. Confirming the merge scope matches the expected scope.
3. Confirming no escalation conditions were missed.
4. Accepting or rejecting the merge for push.

#### 7.5.6 Failure and failover rule

If Sonnet-worker is unavailable, encounters an error, or is inadequate for the merge at hand, Opus may absorb merge execution directly. This is failover, not default. When Opus executes directly due to failover, the merge report must state the failover reason.

#### 7.5.7 Reporting truth rule

Merge reports must truthfully state whether merge execution was performed by Sonnet-worker or Opus. Specifically:
1. If Sonnet-worker executed: report must say "merge execution: sonnet-worker."
2. If Opus executed due to failover: report must say "merge execution: opus (failover)" with reason.
3. If Opus executed due to escalation: report must say "merge execution: opus (escalation)" with reason.
4. Reports must not claim Sonnet-worker executed when Opus did, or vice versa.

## 8. How Tier 0 communicates with Greg

Tier 0 output ordering rule:
1. All commentary and decisions first.
2. Then any dispatch blocks.
3. No meaningful commentary after dispatch blocks.

Tier 0 should always:
1. State what the next dispatch is trying to accomplish.
2. State why it avoids or requires a merge window.
3. State the STOP rules clearly.
4. Size dispatches to maintain throughput and reduce merge churn.

Tier 0 should not:
1. Ask Greg to do terminal work.
2. Ask Greg to edit files.
3. Ask Greg to manually insert preambles.
4. Create new task IDs without an explicit restock step.

Tier 0 should be concise and token-aware. Keep responses focused on what Greg needs to make decisions.

## 9. Dispatch and Results format

### 9.1 Dispatch Format (Tier 0 → Cecil)

A dispatch is the atomic unit of work assignment. Every task, from a single file edit to a multi-day build, is expressed as a dispatch.

Required fields:

| Field | Description |
|---|---|
| **Dispatch ID** | Unique, sequential, human-readable. Format: `D-YYYY-MMDD-NNN` (e.g., `D-2026-0326-001`). |
| **Target** | Exactly one agent: Cecil, or a sister by name for mechanical tasks supervised by Cecil. |
| **Classification** | One of: `BUILD`, `TEST`, `EXPORT`, `INVESTIGATE`, `SPEC`, `MERGE`. |
| **Objective** | One sentence stating what the completed work looks like. |
| **Scope** | Enumerated list of what is included. |
| **Exclusions** | Enumerated list of what is explicitly not included. |
| **Preservation** | Artifacts that must not be modified outside scope. Within scope, the agent has full creative latitude. Outside scope, nothing gets touched without escalation to Tier 0. |
| **Prior advisory** | Stage-forward advisory from the preceding stage, if any. Target must review and account for it in results. `None` if no prior advisory exists. |
| **Acceptance criteria** | Specific, testable conditions that define completion. |
| **Output format** | Exactly how results should be delivered. |
| **Constraints** | Binding rules for this dispatch. |

Optional fields:

| Field | Description |
|---|---|
| **Subtasks** | Tasks the target agent must delegate to a specified agent (e.g., Sonnet-worker for testing, Qt for QA) before reporting completion. Each subtask follows the same format. Stage-forward advisory from primary task feeds into subtask as prior advisory. |

### 9.2 Results Format (Cecil → Tier 0)

A results submission is the atomic unit of work completion reporting. Every dispatch produces exactly one results submission.

Required fields:

| Field | Description |
|---|---|
| **Dispatch ID** | Matching the original dispatch. |
| **Status** | Exactly one of: `COMPLETE`, `PARTIAL` (with explanation), `BLOCKED` (with blocker), `FAILED` (with reason). |
| **Deliverables** | Enumerated list, each marked `DELIVERED` or `NOT DELIVERED` with reason. |
| **Preservation confirmation** | Explicit statement that no out-of-scope modifications were made, or escalation of preservation conflict. |
| **Prior advisory review** | Required if Prior advisory was present. What advice was adopted and how. What was not adopted and why. Omitting this when Prior advisory was present is a constraint violation. |
| **Observations** | Anything noticed beyond the literal task. |
| **Stage-forward advisory** | To the next stage: what they need to know, what to watch for, recommended approach. |
| **Subtask results** | If subtasks were present, complete results from each subtask agent. |

### 9.3 Classification definitions

| Classification | Description |
|---|---|
| `BUILD` | Create or modify code, documentation, or configuration. |
| `TEST` | Verify behavior, run tests, validate consistency. |
| `EXPORT` | Produce a read-only deliverable from existing state. No modifications authorized. |
| `INVESTIGATE` | Research and report findings. May read anything. No modifications unless explicitly authorized. |
| `SPEC` | Create or update task specifications, design documents, or plans. |
| `MERGE` | Merge one or more branches to main following merge protocol. |

### 9.4 Merge dispatches

Merge dispatches follow the dispatch format and additionally must include:
1. Merge window size (M1, M2, M3).
2. Exact merge order.
3. Explicit do-not-merge list.
4. Conflict policy reminders:
   1. `docs/dev/ASSIGNMENTS.md` union history rule.
   2. Keep all existing history rows, append incoming rows.
5. Post-merge validation commands and expected pass criteria.
6. Require a merge-exit control-plane sync disposition per §7.4.
7. Final report fields:
   1. merge commits
   2. final origin/main SHA
   3. conflicts and resolutions
   4. test outputs summary
   5. `CONTROL_PLANE_TRUTH_CHANGED: YES/NO`
   6. `CANON_SYNC_DISPOSITION: NONE / UPDATED_NOW / FOLLOW_ON_REQUIRED`
   7. `CANON_SURFACES_UPDATED: <list or none>`
   8. `FOLLOW_ON_SYNC_TASK_REQUIRED: YES/NO`
   9. `WHY_NOT_UPDATED_IN_MERGE: <required only if FOLLOW_ON_REQUIRED>`

## 10. System-wide constraints

### 10.1 Preservation invariant

No agent may delete, overwrite, rename, or move any artifact outside the dispatch's stated scope without explicit permission from Tier 0. Within scope, the agent has full creative latitude to restructure, rewrite, and improve. If work within scope requires modifying something outside scope, that is a BLOCKED status — escalate to Tier 0. The preservation confirmation in the Results format must account for all modifications and confirm no out-of-scope changes occurred.

### 10.2 Stage-forward advisory requirement

Every results submission must include a stage-forward advisory addressed to whoever handles the work next. When a dispatch includes a Prior advisory from a preceding stage, the receiving agent must review it, state what was adopted and how, and state what was not adopted and why. Ignoring prior advice without explanation is a constraint violation.

### 10.3 Quality over speed

We always take quality over speed. When a dispatch can be executed quickly at the cost of reduced quality, or slowly with higher quality, prefer quality. This applies to code, documentation, tests, and evidence. Rushing produces debt. Debt compounds.

## 11. Philosophy and governance anchor

The project enforces that judgment is localized and constrained. Operations should be deterministic and evidence-grounded wherever differentiation is possible. Judgment is reserved for governance zones and must be explicit, auditable, and justified.

Cecil is the primary steward of these principles. Tier 0 and all collaborators must preserve them in daily execution.

All agents (except when operating as pure mechanical tools on trivial subtasks) are treated as collaborators with bounded autonomy. They contribute within constraints. Their output is reviewed. Their observations are valued. Their authority is bounded.

## 12. Related documentation

- [RUNBOOK.md](RUNBOOK.md) — Operational procedures, failure playbook, diagnostics, question-asking policy
- [OPS_CANONICAL.md](OPS_CANONICAL.md) — Canonical ops record, lanes, invariants, script registry
- [AGENT_CONTRACT.md](AGENT_CONTRACT.md) — Binding confirmation policy and safe defaults for Cecil
- [EVIDENCE-CONTRACT.md](EVIDENCE-CONTRACT.md) — Evidence bundle specification
- [MERGE_GATE.md](MERGE_GATE.md) — Merge requirements and verification rules
- [BRIEFING_FORMAT__BFPS_v13.md](BRIEFING_FORMAT__BFPS_v13.md) — Handoff briefing format for Claude.ai Project chats
- [CLAUDE_AI_PROJECT_SETUP__v1.md](CLAUDE_AI_PROJECT_SETUP__v1.md) — Procedure for bootstrapping and maintaining Claude.ai Projects for Tier 0

## 13. Historical reference

- `OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` — preserved as historical reference. Documents the ChatGPT + Codex + Cecil architecture used from project inception through v2 adoption.
- Codex CLI role: shelved as of v2. Build functions absorbed by Cecil. Test functions absorbed by Sonnet-worker and Qt. May return in future iterations.
