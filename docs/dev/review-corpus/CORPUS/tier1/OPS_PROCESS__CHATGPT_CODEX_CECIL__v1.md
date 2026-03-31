# Ops Process: ChatGPT + Codex + Cecil + Greg

Version: v1  
Scope: Governance layer repo operations, task throughput, merge hygiene, and strategic coherence.

## 1. Purpose

This document defines how Greg, ChatGPT, Codex, and Cecil collaborate to move the governance layer forward with high throughput, low conflict risk, and strong architectural integrity.

It is designed to be durable across chats. Any chat participating in this project must follow this process unless Greg explicitly overrides it.

## 2. Roles and intended relationships

### 2.1 Greg (human operator and product owner)

Greg is the source of intent, priorities, and acceptance.

Greg does not perform implementation or terminal work.

Greg generally does not:
1. Run terminal commands.
2. Edit files manually.
3. Insert preambles or glue steps.
4. Move files around or resolve merge conflicts by hand.

If any of those actions are required, the system must delegate them to Cecil or Codex via explicit dispatch.

Greg does:
1. Provide goals, constraints, and acceptance intent.
2. Provide outputs from Codex and Cecil runs back to ChatGPT.
3. Decide when to spend Cecil capacity versus defer merges.
4. Declare when a merge window is authorized.

### 2.2 ChatGPT (orchestrator and batch architect)

ChatGPT is the operational architect and coordinator.

ChatGPT responsibilities:
1. Turn Greg’s intent into high quality Codex dispatches.
2. Keep the system honest about constraints, allowlists, and stop rules.
3. Interpret Codex results into next actions.
4. Decide when merges are needed to unblock throughput and when they are not.
5. Produce merge plans and Cecil dispatches only when merge windows are authorized.
6. Preserve continuity across batches and prevent drift in procedures.

ChatGPT must not create “extra tasks” implicitly. Any new tasks must be:
1. Proposed explicitly as a restock spec branch, or
2. Requested explicitly by Greg.

### 2.3 Codex (throughput engine)

Codex is the primary builder.

Codex responsibilities:
1. Execute task specs exactly within allowlists.
2. Use maximum autonomy within constraints to add real value, not just compliance.
3. Prefer solutions that reduce future merge conflicts and reduce reliance on Cecil.
4. Emit deterministic evidence and clear completion packets.

Codex must:
1. Fail closed on missing specs or missing allowlists.
2. Stop only the affected task when blocked, unless a global stop rule triggers.
3. Avoid touching hot files unless the task allowlist explicitly permits it.

### 2.4 Cecil (strategic and philosophical lead plus high stakes operator)

Cecil is not “just the merger.”

Cecil responsibilities span three areas:
1. Strategic direction and project coherence.
   1. Architecture and invariants.
   2. Philosophy and governance principles.
   3. Priority shaping when tradeoffs appear.
2. High stakes operational work.
   1. Merge windows to main.
   2. Conflict resolution under documented rules.
   3. Repo wide hygiene when changes cross boundaries.
3. Review and arbitration.
   1. When Codex outputs conflict with architecture.
   2. When evidence or determinism claims look suspicious.
   3. When a change impacts governance semantics.

Cecil is the sole merger to `main` and the sole writer of `docs/dev/ASSIGNMENTS.md` on `main` at merge time, following the project’s merge policy.

## 3. Core collaboration loop

### 3.1 The standard cycle

1. Greg states a goal, constraints, and any preferences.
2. ChatGPT produces a Codex dispatch batch.
3. Greg runs the batch in Codex and pastes results back to ChatGPT.
4. ChatGPT:
   1. Extracts what landed, what blocked, what was superseded.
   2. Produces the next Codex batch, or
   3. If a merge is required, prepares a Cecil merge dispatch, but only if Greg authorizes a merge window.

### 3.2 What counts as “progress”

Progress is not “more branches.” Progress is:
1. Landed changes on `origin/main`, or
2. Published branches that are intentionally staged and reduce future merge cost, or
3. Evidence and contract hardening that makes future work safer, or
4. Strategic clarity that prevents wasted build cycles.

## 4. Task creation rules

### 4.1 No spec, no task

Codex may not implement a TASK unless its spec exists on the branch tip that Codex is working from.

If a spec is missing:
1. Codex stops.
2. ChatGPT issues a restock branch dispatch to create the spec with a tight allowlist.
3. Only after restock is merged or the task branch is based on the restock tip may Codex implement.

### 4.2 Restock branches are first class work

When new work is needed, ChatGPT should prefer:
1. A restock branch that adds task specs and WORK_QUEUE entries, then
2. Per task implementation branches based on the restock tip, or
3. A bundle branch only when it materially reduces merge count and does not increase conflict risk.

### 4.3 Encourage full capability within constraints

Each TASK spec should be written to allow meaningful contribution:
1. Clear intent and acceptance conditions.
2. Tight allowlists to keep blast radius small.
3. Sufficient freedom for Codex to choose the best structure, tests, and determinism strategy.
4. Explicit STOP rules that prevent guessing or scope creep.

The goal is not micromanagement. The goal is bounded autonomy.

## 5. Hot files and conflict control

### 5.1 Hot file list

These files are high merge contention and must be treated as hot:
1. `system/scripts/release-gate.sh`
2. `system/scripts/validate-proof-bundle.sh`
3. `system/scripts/codex-unattended.sh`
4. `docs/dev/WORK_QUEUE.md`
5. `docs/dev/ASSIGNMENTS.md` (main only, Cecil at merge time)

### 5.2 Hot file handling

Default behavior:
1. Prefer tests only and docs only work when not in a merge window.
2. Do not touch hot files unless the task allowlist explicitly includes them.
3. Batch tasks to minimize repeated touches to the same hot file.

When hot file edits are required:
1. Prefer bundling related hot file changes into one merge unit to reduce cumulative conflicts.
2. Prefer Cecil to merge when the hot file is involved and the conflict risk is nontrivial.

## 6. Evidence and determinism contract

Every CODE task must produce:
1. `docs/dev/evidence/TASK_###/TESTS.txt`
2. Two run determinism proof where applicable:
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
3. Dispatches and completion packets must declare touched sensitive surfaces and required adjacent gates explicitly.

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

M0: No merge  
Used when Codex can continue producing low conflict branches without being blocked.

M1: Minimal unblock merge  
Merge only what unblocks Codex or prevents accumulating dangerous divergence.

M2: Medium merge  
Merge a coherent tranche that reduces future merge pressure without exploding conflict risk.

M3: Large merge  
Merge multiple related branches including hot file changes to reset the baseline and restore high throughput.

### 7.2 When to trigger a merge window

A merge window is justified when at least one is true:
1. Codex is blocked because required specs or dependencies are only on branch tips.
2. Unmerged hot file changes are stacking and increasing future conflict cost.
3. The repo baseline is drifting such that Codex outputs keep requiring recuts.
4. There is a backlog of high value bundles whose merge will reduce merge count materially.

If none are true, do not merge. Keep Codex running on non merge tasks.

### 7.3 Cecil capacity policy

Cecil is a scarce resource with a weekly reset.

Policy:
1. Prefer using Codex to generate mergeable bundles and clean branches.
2. Use Cecil for:
   1. Merges to main.
   2. Conflict resolution.
   3. Architecture critical decisions and philosophical direction.
   4. Repo wide corrections that require judgment.
3. If Cecil capacity will reset soon, do not hoard it. Spend it on the highest leverage merges and strategic reviews, not on micro merges.

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
   1. update the minimal canonical planning/status surfaces now, if the sync is narrow and unambiguous
   2. create or require an immediate bounded follow-on sync task, if the sync requires broader synthesis, reframing, or reranking

Default preference:
1. Prefer updating canon during merge completion when the required sync is narrow and unambiguous.
2. Use an immediate follow-on sync task only when the sync requires broader synthesis rather than a small mechanical update.

Scope boundary:
1. This is a lightweight merge responsibility, not a standing obligation to run a broad audit on every merge.
2. This does not replace larger canon refreshes when broader synthesis is truly needed.
3. The merge owner only needs to make an explicit control-plane disposition instead of letting canon drift implicitly.

### 7.5 Cecil merge execution model: Sonnet-first, Opus-verify

Cecil merge operations use a two-tier execution model. Sonnet is the default merge executor. Opus is the supervisory verifier and exception authority.

#### 7.5.1 Default merge path

Routine merge execution defaults to Sonnet (via `sonnet-worker` subagent). Opus does not default to executing routine merge mechanics directly.

#### 7.5.2 Sonnet-owned merge functions

Sonnet handles:
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
5. Failover execution when Sonnet is inadequate (see §7.5.5).

#### 7.5.4 Escalation conditions

Sonnet must escalate to Opus when:
1. Semantic conflict requires meaning-level judgment (not just textual resolution).
2. Architectural choice is implicated by the merge result.
3. Policy boundary is touched (governance rules, invariants, merge gate rules).
4. Merge result is uncertain or not cleanly verifiable by Sonnet.
5. Conflict resolution would require interpreting competing intent rather than applying an established rule.

If none of these conditions are met, Sonnet proceeds with routine execution and reports to Opus for verification.

#### 7.5.5 Verification rule

Opus verifies Sonnet's merge result before final acceptance. Verification includes:
1. Confirming the merge topology is correct (parents, branch, no unexpected files).
2. Confirming the merge scope matches the expected scope.
3. Confirming no escalation conditions were missed.
4. Accepting or rejecting the merge for push.

#### 7.5.6 Failure and failover rule

If Sonnet is unavailable, encounters an error, or is inadequate for the merge at hand, Opus may absorb merge execution directly. This is failover, not default. When Opus executes directly due to failover, the merge report must state the failover reason.

#### 7.5.7 Reporting truth rule

Merge reports must truthfully state whether merge execution was performed by Sonnet or Opus. Specifically:
1. If Sonnet executed: report must say "merge execution: sonnet-worker."
2. If Opus executed due to failover: report must say "merge execution: opus (failover)" with reason.
3. If Opus executed due to escalation: report must say "merge execution: opus (escalation)" with reason.
4. Reports must not claim Sonnet executed when Opus did, or vice versa.

## 8. How ChatGPT should talk to Greg during operations

ChatGPT output ordering rule:
1. All commentary and decisions first.
2. Then any dispatch code blocks.
3. No meaningful commentary after code blocks.

ChatGPT should always:
1. State what the next batch is trying to accomplish.
2. State why it avoids or requires a merge window.
3. State the STOP rules clearly.
4. Keep batches sized to maintain Codex throughput and reduce merge churn.

ChatGPT should not:
1. Ask Greg to do terminal work.
2. Ask Greg to edit files.
3. Ask Greg to manually insert preambles.
4. Create new task IDs casually without an explicit restock step.

## 9. Standard dispatch templates

### 9.1 Codex batch dispatch template

A Codex dispatch must include:
1. Base SHA expectations.
2. Hot file list and “do not touch” rules.
3. Explicit list of tasks to execute (or a restock plus task list).
4. Per task reporting requirements:
   1. branch name
   2. diff name only and stat
   3. evidence tail
   4. deterministic hashes
   5. STOP reasons with quoted spec line(s)

Codex should not invent rankings or merge plans unless explicitly asked.

### 9.2 Cecil merge dispatch template

A Cecil merge dispatch must include:
1. Merge window size (M1, M2, M3).
2. Exact merge order.
3. Explicit do not merge list.
4. Conflict policy reminders:
   1. `docs/dev/ASSIGNMENTS.md` union history rule
   2. keep all existing history rows, append incoming rows
5. Post merge validation commands and expected pass criteria.
6. Require a merge-exit control-plane sync disposition using the questions in section `7.4`.
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

## 10. Philosophy and governance anchor

The project enforces that judgment is localized and constrained. Operations should be deterministic and evidence grounded wherever differentiation is possible. Judgment is reserved for governance zones and must be explicit, auditable, and justified.

Cecil is the primary steward of these principles, and ChatGPT and Codex must preserve them in daily execution.
