# Codex Routed-Runtime Baseline Plan v0

## 1. Purpose

This plan defines the minimum real Codex routed-runtime baseline so that Codex is truthfully set up and operational in a way structurally parallel to Cecil. It does not redesign the Codex system, broaden into general architecture, or force false symmetry with Cecil. It establishes what must be real for "Codex has a routed runtime" to be a true statement.

Cecil's routed-runtime baseline landed on main at `f56c88fc` (2026-03-19). This plan uses the Cecil baseline as a structural reference where appropriate, while respecting the fundamental differences in how Codex operates.

## 2. Current Proven Codex Reality

### Already live

| Component | Location | Evidence |
|---|---|---|
| Unattended task runner | `system/scripts/codex-unattended.sh` | 700-line fail-closed runner with preflight, branch creation, allowed-files enforcement, evidence gating, publish-branch validation |
| Batch generation | `system/scripts/codex-batch.sh` | Read-only task discovery, cap enforcement via `system/ops/limits.json`, outputs `ops/CODEX_BATCH.txt` |
| Throughput loop | `system/scripts/codex-throughput-loop.sh` | Loops batch generation and execution |
| Task spec enforcement | `codex-unattended.sh` `parse_allowed_files()` | Python-based allowed-files parser, forbidden-files guard, changed-files-against-allowed check |
| Evidence gating | `codex-unattended.sh` `cmd_verify_task()` | Requires `docs/dev/evidence/TASK_###/TESTS.txt`, checks against allowed files |
| Branch discipline | `codex-unattended.sh` `validate_publish_branch_name()` | `codex/TASK_###__<sha>` naming enforced, `codex/OPS_*`, `codex/FEATURE_*`, `codex/QUEUE_*` patterns |
| Execution contract injection | `codex-unattended.sh` `cmd_execute_task()` | Prepends OPS_PROCESS doc + forbidden-commands contract to every execution |
| Reception checklist spec | `docs/dev/specs/CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` | Dispatch envelope validation rules (mode, objective, allowed files, acceptance, STOP conditions) |
| QT runner | `system/scripts/qt-runner.sh` | Merge-readiness validation for Codex branches |
| QT job schema | `docs/dev/QT_JOB_SCHEMA.md` | Job format, required keys, output structure |
| Limits configuration | `system/ops/limits.json` | `codex_max_tasks_per_run: 4` |

### Partially live / misrepresented

| Component | Issue |
|---|---|
| Codex execute-task wiring | `cmd_execute_task()` exists but requires `CODEX_EXEC_CMD` environment variable. If not set, fails closed. The actual invocation depends on an external executor command being provided. This is structurally correct (fail-closed) but means execution is not self-contained. |
| Codex reporting in token ledger | Codex runs are not visible in `system/logs/token-ledger.jsonl`. Codex operates as a separate OpenAI product with its own usage tracking. The shared ledger does not capture Codex token usage, model selection, or routing decisions. |
| Codex role in operational-rules.json | Codex is not mentioned in `system/operational-rules.json` at all. The routing rules, tier definitions, and contraindication scanning apply only to Cecil's runtime. Codex has no equivalent runtime routing policy. |

### Documented but not live

| Component | Issue |
|---|---|
| Codex dispatch shape in BFPS | TASK_281 proposes documenting Codex dispatch shape in BFPS v12, but this task has not been executed. |
| Reception checklist deployment | Spec exists (`CODEX_RECEPTION_CHECKLIST__SPEC__v0.md`) but is "Phase 1 specification — not yet operational." Not deployed as project-level instruction. |
| Worker-tier definitions for Codex | No equivalent of Cecil's `.claude/agents/haiku-worker.md` or `sonnet-worker.md` exists for Codex. Codex does not have explicit worker-tier definitions. |
| Delegation discipline for Codex | No documented rules for when Codex should decompose tasks vs. execute monolithically. |

### Unknown

| Component | Status |
|---|---|
| Whether OpenAI Codex supports internal worker-tier routing | Unknown. Codex is an OpenAI product; its internal model routing is opaque to us. We cannot pin subordinate models within Codex the way Cecil pins Haiku/Sonnet workers via `.claude/agents/`. |
| Codex token usage per task | Not captured in our ledger. OpenAI may track this internally but we have no visibility. |
| Codex model selection per task | Unknown whether Codex uses a single model or routes internally. |

## 3. Current Codex Gaps

### Gap 1: No real subordinate-worker invocation paths

Codex executes tasks monolithically. There is no mechanism for Codex to delegate subtasks to cheaper/faster workers. This is fundamentally different from Cecil, where the Agent tool enables model-pinned delegation. Codex, as an OpenAI product, may not support equivalent internal routing.

**Assessment:** This gap may not be closable within Codex itself. The routed-runtime baseline for Codex must define what routing means in the Codex context — which is primarily about how the *system* routes work *to* Codex, not how Codex routes internally.

### Gap 2: No truthful measurement/visibility

Codex task execution produces no entries in our shared token ledger. We cannot answer:
- How many tokens did Codex consume for TASK_###?
- What model did Codex use?
- How long did execution take?
- Did Codex escalate or fail?

The only Codex visibility we have is: branch pushed (yes/no), evidence bundle present (yes/no), allowed-files compliant (yes/no).

### Gap 3: No explicit worker-tier definitions

Cecil has `haiku-worker.md` and `sonnet-worker.md` defining what subordinate tiers do, their constraints, and escalation rules. Codex has no equivalent. The `codex-unattended.sh` script defines Codex's *execution envelope* (preflight, branch, allowed files, evidence) but not its *capability tier* relative to other agents.

### Gap 4: Delegation discipline is ad hoc

Work routing to Codex is decided by ChatGPT (the orchestrator) based on Greg's intent. There is no deterministic routing policy equivalent to Cecil's `scan-q-contraindications.sh` or `routing-enforcement.sh`. The decision of "is this a Codex task or a Cecil task?" is currently a judgment call made in the ChatGPT orchestration chat, not a rules-based determination.

### Gap 5: Codex runtime claims do not exceed reality

Unlike Cecil (where the misrepresentation risk was high — planning docs described multi-model routing that wasn't live), Codex documentation is modest and roughly accurate. `codex-unattended.sh` does what it says. The reception checklist spec is explicitly marked "not yet operational." The risk here is not overclaiming but *underdefinition*.

## 4. Minimum Acceptable Codex End-State

The Codex routed-runtime baseline is complete when all of the following are true:

1. **Codex has an explicit capability-tier definition** that describes what Codex does, what it cannot do, and when work should escalate from Codex to Cecil. This is the Codex equivalent of Cecil's worker agent definitions.
2. **The system has a deterministic routing policy** for classifying incoming work as Codex-eligible vs. Cecil-required vs. shared. This replaces the current ad hoc judgment.
3. **Codex task execution produces truthful completion evidence** that is visible to Cecil and Greg without needing to inspect Codex internals. At minimum: task ID, branch, status, files changed, evidence produced, execution duration (wall clock).
4. **The routing decision for each task is recorded** so we can audit why work went to Codex vs. Cecil. This is the Codex equivalent of Cecil's token ledger routing entries.
5. **QT validation is wired as the Codex-side verification tier.** QT already exists for merge-readiness checks. The baseline must confirm QT is live and usable as Codex's equivalent of Cecil's subordinate verification path.
6. **The reception checklist is operational**, not just specified. Codex must actually validate dispatch envelopes before beginning work.

## 5. Capability Map by Path

### Codex parent session

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Runtime | OpenAI Codex (opaque model selection) | No change to internals | Stays |
| Execution envelope | `codex-unattended.sh` with fail-closed guards | No change | Stays |
| Capability tier | Implicitly "throughput engine" per OPS_PROCESS v1 | Explicit capability-tier definition document | New |
| Constraints | Defined in OPS_PROCESS v1 §2.3 + reception checklist | Consolidated into capability-tier definition | Changes (consolidation) |

### QT path

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Runner | `system/scripts/qt-runner.sh` | No change | Stays |
| Job schema | `docs/dev/QT_JOB_SCHEMA.md` | No change | Stays |
| Role | Merge-readiness validation | Explicit: Codex-side verification tier | Clarified |
| Evidence | `docs/dev/evidence/QT/<JOB_ID>/` | No change | Stays |
| Invocation | Manual / dispatch-driven | No change for baseline | Stays |

### Sisters/qwen path

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Relevance to Codex | Not relevant — qwen/sisters are Cecil-side local models | Stays not relevant to Codex | Stays |
| Codex cannot invoke qwen | Correct — Codex runs in OpenAI's environment | No change | Stays |

### Hooks/logging/reporting surfaces

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Token ledger | Does not capture Codex usage | Codex completion records logged to a parallel surface | New |
| Statusline | Does not show Codex metrics | Not required for baseline (Cecil statusline is Cecil-only) | Stays |
| Routing audit | Does not cover Codex dispatch decisions | Codex routing decisions recorded in dispatch log | New |

### Branch/dispatch discipline surfaces

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Branch naming | `codex/TASK_###__<sha>` enforced | No change | Stays |
| Dispatch format | OPS_PROCESS v1 §9.1 + reception checklist (spec only) | Reception checklist operational | Changes |
| Batch generation | `codex-batch.sh` generates `CODEX_BATCH.txt` | No change | Stays |
| Completion packets | Codex produces per-task evidence bundles | Add structured completion packet with routing metadata | Changes |

## 6. What Should Match Cecil and What Should Differ

### Should match

| Property | Why |
|---|---|
| Truthful reporting | Both agents must truthfully report what they did, not what they aspire to. No false claims of routing that didn't occur. |
| Explicit capability-tier definitions | Both agents need documented definitions of what they do, their constraints, and escalation paths. Cecil has `haiku-worker.md` / `sonnet-worker.md`; Codex needs its own tier definition. |
| Bounded delegation rules | Both agents need explicit rules for what they handle directly vs. what escalates. Ad hoc judgment should be replaced with deterministic classification where possible. |
| Evidence-gated completion | Both agents must produce verifiable evidence of task completion. Cecil uses ledger entries; Codex uses evidence bundles. |
| Fail-closed on missing specs | Both already do this. Must be preserved. |

### Should differ

| Property | Why |
|---|---|
| Authority domain | Cecil is the authority/governance agent (merge, architecture, strategy). Codex is the throughput engine (bounded task execution). These are different roles, not different tiers of the same role. |
| Branch ownership | Cecil merges to main. Codex pushes to `codex/*` branches. This is correct and must not change. |
| Worker pool | Cecil has internal workers (haiku-worker, sonnet-worker, qwen/sisters). Codex does not have internal workers and should not be forced to simulate them. |
| Verification rigor | Cecil produces ledger entries with per-token attribution. Codex produces coarser evidence bundles (TESTS.txt, DIFF.patch). Codex verification is at the task level, not the token level. This is appropriate given Codex's opaque internals. |
| Routing mechanism | Cecil routes internally via Agent tool + ollama-call.sh. Codex routing is *external* — ChatGPT/Greg decides what goes to Codex. The Codex baseline should formalize the external routing rules, not create internal routing that doesn't exist. |
| Model transparency | Cecil's model usage is fully visible (Opus parent, Haiku/Sonnet workers, qwen). Codex's model is opaque (OpenAI selects internally). The baseline should not pretend Codex model selection is transparent. |

## 7. Required Corrections to Existing Codex Infrastructure

### Correction 1: Reception checklist deployment

**Current:** Spec exists at `docs/dev/specs/CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` but is explicitly "not yet operational."
**Required:** Deploy as operational Codex instruction. The checklist must be part of every dispatch preamble or Codex project-level configuration.
**Files:** New operational instruction derived from existing spec.

### Correction 2: Codex capability-tier definition gap

**Current:** Codex's role is defined across OPS_PROCESS v1 §2.3 (4 bullet points), the reception checklist spec, and `codex-unattended.sh` behavior. No single document defines Codex's capability tier.
**Required:** Consolidate into a single explicit capability-tier definition, parallel to Cecil's worker agent definitions.
**Files:** New: `docs/dev/CODEX_CAPABILITY_TIER__v0.md`

### Correction 3: Completion packet structure

**Current:** Codex evidence bundles contain TESTS.txt, DIFF.patch, SUMMARY.md, etc. These are file-oriented, not structured routing metadata.
**Required:** Add a structured completion packet format that includes: task ID, branch, status, execution duration, files changed count, evidence hash, routing decision reference.
**Files:** Define in capability-tier document; implement in `codex-unattended.sh` finalize-task.

## 8. Required New Codex Runtime Capabilities

### New Capability 1: Codex capability-tier definition document

**What:** A single document defining Codex's role, constraints, escalation rules, and acceptance criteria in the same structural format as Cecil's worker definitions.
**Why:** Without this, Codex's role is scattered across multiple documents. The routing decision "is this a Codex task?" has no single authoritative reference.
**Form:** `docs/dev/CODEX_CAPABILITY_TIER__v0.md`

### New Capability 2: Codex routing classification rules

**What:** Deterministic rules for classifying incoming work as Codex-eligible, Cecil-required, or shared.
**Why:** Currently ChatGPT makes this judgment ad hoc. A rules-based classification reduces misrouting and makes dispatch decisions auditable.
**Form:** Section within capability-tier document or standalone classification rules document.

### New Capability 3: Codex completion packet with routing metadata

**What:** Structured completion output from `codex-unattended.sh` that includes routing decision reference, execution metadata, and evidence summary.
**Why:** Without this, the system has no audit trail for why work went to Codex or how long it took.
**Form:** JSON or structured text output from `cmd_finalize_task()`.

### New Capability 4: QT verification path confirmation

**What:** Confirm QT runner is live and usable as Codex's verification tier. Run one bounded QT job as proof.
**Why:** QT is documented but evidence of recent live use is limited. The baseline must prove QT works, not just that the schema exists.
**Form:** One QT job execution with evidence.

## 9. Routing/Delegation Decision Model for Codex

### How the system should classify incoming work

```
Incoming work item
    |
    +-- Does it require merge authority?         --> Cecil only
    +-- Does it require architecture decisions?  --> Cecil only
    +-- Does it require governance judgment?     --> Cecil only
    +-- Does it require conflict resolution?     --> Cecil only
    |
    +-- Is it a bounded task with:
    |   - explicit spec
    |   - explicit allowed files
    |   - explicit acceptance criteria
    |   - no hot-file dependencies
    |   --> Codex eligible
    |
    +-- Is it a bounded task that touches hot files?
    |   --> Codex eligible ONLY if hot files are explicitly in allowed list
    |       AND merge is pre-authorized
    |
    +-- Is it investigation/analysis with no code changes?
    |   --> Codex eligible (Investigate mode)
    |
    +-- Is it multi-agent coordination?
    |   --> ChatGPT orchestration + Codex/Cecil dispatch
    |
    +-- Does it require real-time judgment during execution?
    |   --> Cecil (Codex is unattended, cannot pause for judgment)
    |
    +-- Unclear or mixed scope?
    |   --> ChatGPT proposes decomposition; Greg decides
    |
    +-- Fallback: Greg decides
```

### Codex internal delegation model

Codex does not have internal delegation. It executes tasks monolithically. This is structurally correct:
- Codex runs in OpenAI's environment with opaque model selection
- We cannot pin subordinate models within Codex
- Forcing internal delegation would create false complexity

The "routing" for Codex is *what arrives at Codex*, not what happens inside it.

### QT as Codex-side verification

QT serves as the verification/validation tier for Codex work:
- QT validates merge-readiness of Codex branches
- QT runs are dispatched separately from Codex task execution
- QT is to Codex roughly what haiku-worker is to Cecil: a cheaper verification pass

## 10. Truth Model for Codex Reporting/Measurement

### What Codex completion packets must truthfully show

| Field | Required | Purpose |
|---|---|---|
| `task_id` | YES | Which task was executed |
| `branch` | YES | Where the work landed |
| `status` | YES | `COMPLETE`, `BLOCKED`, `FAILED`, `STOPPED` |
| `files_changed` | YES | List of files modified |
| `evidence_path` | YES | Path to evidence bundle |
| `evidence_present` | YES | Boolean: does evidence bundle exist and have content |
| `allowed_files_compliant` | YES | Boolean: all changes within allowed files |
| `forbidden_files_clean` | YES | Boolean: no forbidden files touched |
| `base_sha` | YES | SHA the branch was created from |
| `head_sha` | YES | Final commit SHA |
| `wall_clock_seconds` | RECOMMENDED | Execution duration (from begin-task to finalize-task) |
| `routing_decision` | RECOMMENDED | Why this task was sent to Codex (reference to dispatch) |
| `model_used` | UNKNOWN | Cannot be determined — Codex model selection is opaque |

### What we explicitly cannot report

- Codex token usage (not visible to us)
- Codex internal model selection (opaque)
- Codex internal routing decisions (if any)

**This is honest.** The truth model for Codex says "we know what went in and what came out, but the internal execution is opaque." This is different from Cecil, where internal execution is fully transparent. The baseline must not pretend Codex internals are transparent.

## 11. Verification Plan

### Verification 1: Capability-tier definition is accurate

- Read the capability-tier document
- Confirm each claimed capability against `codex-unattended.sh` behavior
- Confirm each escalation rule against OPS_PROCESS v1
- Confirm no overclaiming

### Verification 2: Routing classification rules work

- Take 5 recent tasks that went to Codex and 5 that went to Cecil
- Apply the classification rules
- Confirm the rules produce the correct routing for all 10
- If any misclassification, refine rules

### Verification 3: Completion packet captures truthful metadata

- Run one Codex task through `codex-unattended.sh` with completion packet output
- Verify all required fields are present and accurate
- Verify no fields claim information we don't actually have

### Verification 4: QT verification path is live

- Run one QT merge-readiness job against an existing Codex branch
- Verify QT produces correct pass/fail output
- Verify evidence is written to expected location

### Verification 5: Reception checklist is operational

- Send one dispatch with a deliberately missing required element
- Confirm Codex fails closed with correct missing-element report
- Send one complete dispatch
- Confirm Codex proceeds

## 12. Ordered Implementation Lanes

### Lane 1: Codex Capability-Tier Definition

Define Codex's role, constraints, escalation rules, and capability boundaries in a single authoritative document.

| Task | Scope |
|---|---|
| Write `CODEX_CAPABILITY_TIER__v0.md` | Consolidate from OPS_PROCESS v1, reception checklist spec, codex-unattended.sh behavior |
| Include routing classification rules | Deterministic rules for Codex-eligible vs. Cecil-required |
| Include escalation paths | When and how Codex work escalates to Cecil |

**Depends on:** Nothing. Can start immediately.
**Files:** New: `docs/dev/CODEX_CAPABILITY_TIER__v0.md`

### Lane 2: Completion Packet Structure

Add structured completion output to `codex-unattended.sh` so every task produces auditable routing metadata.

| Task | Scope |
|---|---|
| Define completion packet JSON schema | Fields from Section 10 |
| Add packet emission to `cmd_finalize_task()` | Emit JSON to `docs/dev/evidence/TASK_###/COMPLETION_PACKET.json` |
| Add wall-clock timing to `cmd_run_one()` | Capture start/end timestamps |

**Depends on:** Lane 1 (for field definitions).
**Files:** Modified: `system/scripts/codex-unattended.sh`; New: completion packet schema reference in capability-tier doc.

### Lane 3: Reception Checklist Operational Deployment

Move the reception checklist from spec to operational reality.

| Task | Scope |
|---|---|
| Extract operational instruction from spec | Concise validation rules from Sections 2-6 |
| Deploy as dispatch preamble or Codex instruction | Integrate with `cmd_execute_task()` contract injection |
| Test with one deliberately incomplete dispatch | Verify fail-closed behavior |

**Depends on:** Nothing. Can run in parallel with Lane 1.
**Files:** Modified: `system/scripts/codex-unattended.sh` (contract injection); possibly new instruction file.

### Lane 4: QT Verification Path Confirmation + End-to-End Proof

Confirm QT is live and run the full verification plan from Section 11.

| Task | Scope |
|---|---|
| Run one QT merge-readiness job | Prove QT works |
| Run one full Codex task with completion packet | End-to-end proof |
| Verify routing classification against historical tasks | 10-task audit |
| Document verification results | Completion record |

**Depends on:** Lanes 1-3 complete.
**Files:** New: `docs/dev/CODEX_ROUTED_RUNTIME_BASELINE__COMPLETION_RECORD__v0.md`

## 13. Recommended Execution Order

```
Lane 1: Codex Capability-Tier Definition     <-- START HERE
    |
    +-- Can begin immediately
    +-- No dependencies
    +-- Establishes authoritative reference for all subsequent work
    |
    v
Lane 3: Reception Checklist Deployment       <-- CAN OVERLAP WITH LANE 1
    |
    +-- Independent of Lane 1 content
    +-- Makes Codex execution envelope honest
    |
    v
Lane 2: Completion Packet Structure          <-- AFTER LANE 1
    |
    +-- Needs field definitions from Lane 1
    +-- Touches codex-unattended.sh (hot file)
    |
    v
Lane 4: QT + End-to-End Verification        <-- LAST
    |
    +-- Needs Lanes 1-3 complete
    +-- Proves the baseline is real
```

## 14. Risks and Failure Modes

### Risk 1: Fake delegation (HIGH)

Creating routing classification rules that are never actually consulted. If ChatGPT continues making ad hoc routing decisions, the rules become shelf-ware. **Mitigation:** Make the rules simple enough that following them is easier than ignoring them. Integrate into dispatch templates.

### Risk 2: False reporting (MEDIUM)

Completion packets that claim information we don't have (e.g., fabricated token counts or model attribution for Codex). **Mitigation:** The truth model in Section 10 explicitly defines what is unknown. Completion packets must not fill unknown fields with estimates.

### Risk 3: Branch discipline drift (LOW)

Codex branch naming and allowed-files enforcement is already strong. Risk is low because `codex-unattended.sh` enforces mechanically. **Mitigation:** No additional mitigation needed; existing guards are adequate.

### Risk 4: Stale workspace drift (MEDIUM)

Codex branches that sit unmerged accumulate divergence from main. This is an existing operational risk, not a baseline risk. **Mitigation:** Existing merge-window policy in OPS_PROCESS v1 §7 addresses this.

### Risk 5: Worker overuse (LOW for Codex)

Unlike Cecil (where delegating everything to Haiku/Sonnet wastes capability), Codex has no internal workers. The risk is sending *too much* to Codex — work that should go to Cecil. **Mitigation:** Routing classification rules in Lane 1.

### Risk 6: Cost blowout (MEDIUM)

Codex token costs are opaque. We cannot monitor per-task cost. **Mitigation:** `codex_max_tasks_per_run: 4` cap in `limits.json` bounds batch size. Wall-clock timing in Lane 2 provides a proxy for cost. This is the best we can do given Codex's opacity.

### Risk 7: Parent verification overload (MEDIUM)

Cecil must review and merge all Codex branches. High Codex throughput can overwhelm Cecil's merge budget. **Mitigation:** OPS_PROCESS v1 §7.3 Cecil capacity policy; QT as pre-merge verification reduces Cecil review burden.

## 15. Immediate Next Implementation Task Recommendation

**Lane 1, Task 1: Write `CODEX_CAPABILITY_TIER__v0.md`**

This is the first bounded task. It produces the authoritative reference document that all subsequent lanes depend on.

Scope:
- Consolidate Codex role from OPS_PROCESS v1 §2.3
- Consolidate execution constraints from `codex-unattended.sh`
- Include routing classification rules (Codex-eligible vs. Cecil-required)
- Include escalation paths (when Codex work fails back to Cecil)
- Include capability boundaries (what Codex cannot do)
- Reference but do not duplicate the reception checklist spec

Allowed files:
- `docs/dev/CODEX_CAPABILITY_TIER__v0.md` (new)
- `docs/dev/evidence/` (verification)

This task is Codex-executable (bounded, specifiable, no hot files, no merge required).

**Second task (Lane 3, can overlap):** Deploy reception checklist as operational instruction.

**Third task (Lane 2, after Lane 1):** Add completion packet emission to `codex-unattended.sh`.
