# Cecil Routed-Runtime Completion Plan v0

## 1. Purpose

This plan exists to complete the routed-runtime baseline so that Cecil's actual runtime behavior matches the planning language and operational rules already documented. It does not redesign the routing architecture — that architecture already exists. It identifies the gaps between what is documented/configured and what is live, then defines the minimum implementation work to close those gaps.

The end-state is a system where "Cecil uses multi-model routing" is a true operational statement, not an aspirational one.

## 2. Current Proven Reality

### Already live

| Component | Location | Evidence |
|---|---|---|
| Two-stage task router | `system/scripts/route-task.sh` | Executable script, 334 lines, stages 1+2 implemented |
| Stage 1 deterministic Q-scan | `system/scripts/lib/scan-q-contraindications.sh` | Pattern-match Q1–Q4, no model involved |
| Stage 2 qwen H-classifier | `system/scripts/lib/ollama-call.sh` → `qwen2.5:14b` | Calls Ollama API, returns tier classification |
| Ollama wrapper with ledger logging | `system/scripts/lib/ollama-call.sh` | Auto-escalation lq→bq, token logging on every call |
| Sister-managed plan dispatch | `system/scripts/dispatch-plan.sh` | Conflict-of-interest dispatcher selection, structured output |
| Routing enforcement hook | `system/scripts/routing-enforcement.sh` | UserPromptSubmit hook, fires on pattern match, injects routing reminders |
| Routing audit hook | `system/scripts/routing-audit.sh` | Stop hook, flags Opus doing qwen-class work |
| Subagent usage logger | `system/scripts/log-subagent-usage.sh` | SubagentStop hook, appends to ledger |
| Token ledger | `system/logs/token-ledger.jsonl` | JSONL append-only, tracks all providers/models |
| Statusline aggregator | `system/scripts/statusline.sh` | Aggregates from ledger, shows per-model percentage |
| Operational rules | `system/operational-rules.json` | 59.6KB, compute_routing + routing_system sections |
| Routing documentation | `system/docs/routing-overview.md` | Architecture, tiers, delegation pattern |

### Partially live / misrepresented

| Component | Issue |
|---|---|
| Subagent model attribution | `log-subagent-usage.sh` hardcodes all subagent completions as `claude-haiku`. This is accidentally correct for the built-in Explore subagent (which runs on Haiku by default) but incorrect for general-purpose subagents (which inherit the parent model, Opus 4.6). Ledger entries are partially false. |
| Statusline Haiku percentage | Statusline counts `provider == "subagent"` as Haiku. This overcounts Haiku when general-purpose (Opus-inherit) subagents are used. |
| Dispatch execution loop | `dispatch-plan.sh` outputs structured routing instructions but does NOT actually execute haiku/opus steps. Lines 174–195 print `[Would execute via: ...]` stubs. Only lq/bq steps could theoretically be executed via `ollama-call.sh`. |
| Operational-rules Cecil model | `operational-rules.json` defines Sonnet as Cecil's model. Current session is Opus 4.6. This is a policy/reality divergence — either the rules need updating to reflect Opus, or the session model needs to match the rules. |
| Claude Code subagent model selection | Claude Code natively supports per-subagent model selection via the `model` field in agent definitions (`.claude/agents/` markdown files). Built-in subagents already use this: Explore defaults to Haiku, statusline-setup defaults to Sonnet. However, no custom model-pinned agents have been defined in any Cecil environment. The `.claude/agents/` directory does not exist at project, cecil-repo, or user level. |

### Documented but not live

| Component | Issue |
|---|---|
| Model-pinned custom subagents | Claude Code supports custom agents with explicit `model: sonnet` or `model: haiku` in `.claude/agents/` markdown files. No such agents have been created. This is the gap between having the capability and using it. |
| Dispatch haiku/opus execution | `dispatch-plan.sh` recognizes `haiku` and `opus` executor labels but cannot execute them. Stubs only. |
| Cecil delegation discipline | Routing overview says "Opus acts as thin router/supervisor." In practice, Cecil executes all work directly. No decomposition into delegatable subtasks occurs, except occasional use of the Explore subagent (which does run on Haiku). |

### Now resolved (previously unknown)

| Component | Resolution |
|---|---|
| Whether Claude Code supports per-subagent model selection | **YES.** Documented capability. Agent definition files in `.claude/agents/` support `model: sonnet`, `model: haiku`, `model: opus`, full model IDs, or `inherit` (default). Built-in subagents already use different models (Explore=Haiku, statusline-setup=Sonnet). No external API wrapper required. |

## 3. Current Gaps

### Gap 1: No model-pinned custom subagents defined

Claude Code natively supports Sonnet and Haiku subagents via agent definition files in `.claude/agents/`. The `.claude/agents/` directory does not exist anywhere in the Cecil environment. No custom agents with `model: sonnet` or `model: haiku` have been created. The built-in Explore subagent (Haiku) is the only non-parent-model subagent currently used, and it is used incidentally rather than as a deliberate routing choice.

### Gap 2: Subagent model misattribution

`log-subagent-usage.sh` labels all subagent completions as `claude-haiku`. This is correct for Explore subagents (Haiku) but incorrect for general-purpose subagents (Opus via inherit). The hook cannot distinguish subagent types.

### Gap 3: Dispatch execution stubs

`dispatch-plan.sh` cannot execute haiku or opus steps. It prints routing instructions but the execution loop is incomplete. This means the sister-managed dispatch pattern is a planning tool, not an execution tool.

### Gap 4: No delegation discipline enforcement

Cecil receives tasks and executes them directly. No mechanism decomposes a task into subtasks, classifies them by tier, and delegates eligible subtasks to lower tiers. The routing enforcement hook injects reminders, but reminders are advisory — they do not force routing.

### Gap 5: Operational-rules model mismatch

`operational-rules.json` says Cecil is Sonnet. Cecil is currently Opus 4.6. This creates confusion about what the rules actually govern.

### Gap 6: Statusline truth gap

The statusline accurately reflects ledger contents, but the ledger contains false labels (subagents logged as Haiku when they are Opus). The statusline is honest to its input; its input is dishonest.

## 4. Minimum Acceptable End-State

The routed-runtime baseline is complete when all of the following are true:

1. **Cecil (Opus parent) can invoke qwen/sisters for text-processing subtasks** and receive structured results. (Already live via `ollama-call.sh`.)
2. **Cecil (Opus parent) can invoke at least one Claude subordinate tier** (Sonnet or Haiku) for tool-capable subtasks and receive structured results. The invocation mechanism uses Claude Code's native model-pinned custom subagents (`.claude/agents/` with explicit `model` field).
3. **The token ledger accurately attributes model usage.** No hardcoded model labels. Each entry reflects the actual model that ran.
4. **The statusline accurately reflects real model distribution.** Percentages correspond to actual model usage, not misattributed labels.
5. **`dispatch-plan.sh` can execute at least lq/bq/haiku steps end-to-end,** not just output routing instructions.
6. **`operational-rules.json` accurately reflects the current Cecil model** (Opus 4.6 or whatever is actually running).
7. **Cecil exercises delegation discipline in at least one documented work class** — e.g., file exploration, data extraction, or validation tasks get routed to an appropriate subordinate instead of being executed directly by Opus.
8. **An end-to-end verification exists** proving that a real task was routed, executed by a subordinate, logged to the ledger, and reflected in the statusline.

## 5. Capability Map by Path

### Opus parent session

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Model | Opus 4.6 via Claude Code | No change | Stays |
| Role | Executes everything directly | Thin router/supervisor, delegates eligible subtasks | Changes (discipline) |
| Tools | All Claude Code tools available | No change | Stays |

### Qwen/sisters external invocation path

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Invocation | `ollama-call.sh` via Bash tool | No change | Stays |
| Models | qwen2.5:7b-instruct, qwen3:14b | No change | Stays |
| Ledger logging | Automatic, provider=ollama | No change | Stays |
| Statusline | Lq%, Bq% from ledger | No change | Stays |
| Execution | Live, tested | No change | Stays |

### Claude subordinate invocation path (via Claude Code native subagents)

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Invocation | Agent tool with built-in types only | Agent tool with custom model-pinned agents | Configuration (new agent definitions) |
| Agent definitions directory | `.claude/agents/` does not exist | `.claude/agents/` with Sonnet and Haiku worker agents | Configuration (create directory + files) |
| Models available | Explore=Haiku (built-in), general-purpose=inherit (Opus) | Sonnet worker, Haiku worker (custom), plus existing built-ins | Configuration |
| Ledger logging | `log-subagent-usage.sh` logs all as `claude-haiku` | Log with correct model_id per subagent type | Correction |
| Statusline | S% exists but always 0; H% includes Opus subagents | S% reflects real Sonnet usage; H% reflects only real Haiku usage | Correction (once attribution is fixed) |
| Return contract | Agent tool already returns structured results | No change | Stays |

### Subagent path (Claude Code Agent tool — current behavior)

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Built-in Explore | Runs on Haiku (correct) | No change | Stays |
| Built-in general-purpose | Runs on Opus (inherits parent) | No change for default; custom agents provide model-pinned alternatives | Stays + new agents |
| Ledger logging | `log-subagent-usage.sh` logs all as `claude-haiku` | Log with correct model_id (Haiku for Explore, Opus for general-purpose, Sonnet/Haiku for custom agents) | Correction |
| Statusline | All subagents counted as Haiku | Counted by actual model_id | Correction |

### Hooks

| Hook | Current state | Required final state | Action |
|---|---|---|---|
| routing-enforcement.sh | Live, injects reminders | No change | Stays |
| routing-audit.sh | Live, flags violations | No change | Stays |
| log-subagent-usage.sh | Live, partially misattributes model (correct for Explore/Haiku, wrong for general-purpose/Opus) | Correct model attribution by detecting subagent type or model from hook input | Correction |
| statusline.sh | Live, reflects ledger | Sonnet tracking added, correct Haiku counting needed | Correction |

### Ledger

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Schema | Supports all providers/models | No change | Stays |
| Claude Code entries | Accurate (Opus, provider=claude_code) | No change | Stays |
| Ollama entries | Accurate (qwen models, provider=ollama) | No change | Stays |
| Subagent entries | Partially misattributed (all logged as claude-haiku; correct for Explore, wrong for general-purpose) | Correct attribution by subagent type | Correction |

### Statusline

| Aspect | Current state | Required final state | Action |
|---|---|---|---|
| Model label (Opus) | Accurate | No change | Stays |
| S% (Sonnet) | Always 0 (no Sonnet usage) | Reflects real Sonnet usage once path exists | Stays (becomes real) |
| H% (Haiku) | Overcounts (includes Opus subagents) | Reflects only actual Haiku usage | Correction |
| Lq%, Bq% | Accurate | No change | Stays |
| Qt% | Accurate | No change | Stays |

## 6. Required Corrections to Existing Infrastructure

### Correction 1: Fix subagent model attribution in log-subagent-usage.sh

**Current:** Line 46 hardcodes `--arg model "claude-haiku"`.
**Required:** Detect actual subagent model from hook input. Claude Code subagents use different models depending on type: Explore defaults to Haiku, general-purpose inherits the parent (Opus 4.6), and custom agents use their pinned model. The hook must distinguish these cases.
**Approach:** The SubagentStop hook input JSON may include `subagent_type` or model information. If `subagent_type` is available, map it: `Explore` → `claude-haiku`, `general-purpose` → parent model (read from statusline state file), custom agents → their pinned model. If subagent_type is not available in hook input, read from the agent transcript or fall back to parent model with an `attribution_uncertain` flag.
**Files:** `system/scripts/log-subagent-usage.sh`

### Correction 2: Fix statusline Haiku counting

**Current:** `statusline.sh` line 117 counts `(.model_id | contains("haiku")) or (.provider == "subagent")` as Haiku.
**Required:** Remove `(.provider == "subagent")` from the Haiku selector. Subagent entries will be counted under whatever model_id they carry (once Correction 1 lands).
**Files:** `system/scripts/statusline.sh`

### Correction 3: Update operational-rules.json Cecil model reference

**Current:** `compute_routing.tiers.sonnet` is defined as Cecil's model. `compute_routing.delegation_pattern.purpose` says "Sonnet (Cecil)."
**Required:** Either update to reflect Opus 4.6 as Cecil's current model, or add an explicit note that the Cecil model varies by session configuration. The tier definitions should distinguish between the policy tier (Sonnet-class work) and the actual session model.
**Files:** `system/operational-rules.json`

### Correction 4: Fix dispatch-plan.sh execution stubs

**Current:** Lines 174–195 print placeholder messages for haiku/opus executors.
**Required:** Wire lq/bq steps to actual `ollama-call.sh` execution. Wire haiku steps to the new Claude subordinate invocation path (once built). Opus steps return to parent.
**Files:** `system/scripts/dispatch-plan.sh`

## 7. Required New Runtime Capabilities

### New Capability 1: Model-pinned custom subagent definitions

**What:** Claude Code agent definition files in `.claude/agents/` that pin specific models for subordinate work classes.
**Why:** Claude Code natively supports per-subagent model selection. The capability exists but no custom agents have been defined. Creating agent definitions is the minimum action needed to enable Sonnet and Haiku as deliberate subordinate tiers.
**No external API wrapper required.** Claude Code handles model invocation, token accounting, and result return internally. The existing SubagentStop hook handles logging (once attribution is corrected in Lane 1).

**Required agent definitions (minimum):**

```
~/.claude/agents/sonnet-worker.md     (or project-level .claude/agents/)
~/.claude/agents/haiku-worker.md
```

**sonnet-worker.md:**
```markdown
---
name: sonnet-worker
description: Sonnet-tier subordinate for judgment-adjacent subtasks, structured validation, and draft generation
model: sonnet
tools: Read, Glob, Grep, Bash
---

You are a subordinate worker agent. Complete the delegated task and return structured results.
If the task requires authority-level judgment or merge decisions, return ESCALATE: [reason].
```

**haiku-worker.md:**
```markdown
---
name: haiku-worker
description: Haiku-tier subordinate for file exploration, data extraction, validation, and routine execution
model: haiku
tools: Read, Glob, Grep, Bash
---

You are a subordinate worker agent. Complete the delegated task and return structured results.
If the task requires judgment beyond routine execution, return ESCALATE: [reason].
```

**Invocation from Cecil:** `Agent(subagent_type="sonnet-worker", prompt="...")` or `Agent(subagent_type="haiku-worker", prompt="...")`

**Prerequisites:** None. No API key configuration needed — Claude Code manages Claude API access through the existing session/subscription.

**Files:** New: `~/.claude/agents/sonnet-worker.md`, `~/.claude/agents/haiku-worker.md` (or project-level equivalents)

### New Capability 2: Delegation discipline activation

**What:** Cecil must actively decompose eligible subtasks and route them through the appropriate invocation path. This is a behavioral change, not a script change.
**How:** Define a small set of work classes where delegation is mandatory (not optional):
- **File exploration** (>3 searches): Must use Agent tool (already instrumented by routing-audit.sh)
- **Data extraction/parsing**: Must use `ollama-call.sh` with qwen
- **Validation of structured output**: Must use qwen or haiku
- **Routine file reads for context gathering**: May use Agent tool

This does not require new scripts. It requires Cecil to follow the existing routing policy when processing tasks.

**Enforcement:** The routing-audit.sh hook already flags violations. Strengthening enforcement from audit-only to advisory-with-explicit-acknowledgment would help.

## 8. Routing Decision Execution Model

### Where routing actually happens at runtime

```
User Task arrives
    │
    ├─ [Hook: routing-enforcement.sh] ─── injects routing reminder if pattern matches
    │
    ▼
Cecil (Opus parent) receives task
    │
    ├─ Is this a pure-judgment/authority task? ──── YES → Cecil handles directly
    │
    ├─ Does this contain decomposable subtasks? ── YES → Decompose
    │   │
    │   ├─ Text processing / extraction ───── route to ollama-call.sh (qwen)
    │   ├─ Tool-capable subtasks ────────────── route to Agent(sonnet-worker) or Agent(haiku-worker)
    │   ├─ Parallel exploration ───────────── route to Agent(Explore) [already Haiku]
    │   └─ Return results to Cecil for synthesis
    │
    └─ Single-step task within Cecil's tier ── Cecil handles directly
    │
    ▼
Cecil synthesizes results, responds to user
    │
    ├─ [Hook: routing-audit.sh] ─── flags if Cecil did qwen-class work directly
    └─ [Hook: statusline.sh] ────── updates ledger-based display
```

### Policy/rules layer
`operational-rules.json` defines tiers, contraindications, escalation triggers. This is the reference. It does not execute.

### Invocation layer
- `ollama-call.sh`: Executes qwen/sister tasks. Live.
- Agent tool with built-in Explore: Executes Haiku exploration subtasks. Live (but misattributed in ledger — hook logs all subagents as Haiku regardless of type).
- Agent tool with custom model-pinned agents: Executes Sonnet/Haiku subordinate subtasks. NOT YET CONFIGURED (agent definitions not created).
- Agent tool with general-purpose: Executes Opus subtasks (inherits parent model). Live.

### Parent verification/synthesis layer
Cecil reviews subordinate outputs before using them. For untrusted tiers (qwen), output validation is required per policy. For trusted tiers (Sonnet, Haiku), output is accepted unless flagged.

### Fallback/no-progress behavior
- If `ollama-call.sh` fails: Cecil handles directly (logged as routing fallback).
- If a model-pinned subagent fails or returns ESCALATE: Cecil handles directly.
- If Agent tool fails: Cecil handles directly.
- All fallbacks must be logged with escalation_reason in the ledger.

## 9. Ledger/Statusline Truth Model

### What each ledger field means

| Field | Meaning |
|---|---|
| provider | Who invoked the model: `claude_code` (main session), `ollama` (local script), `subagent` (Agent tool — includes all subagent types: Explore, general-purpose, and custom model-pinned agents) |
| model_id | The actual model that ran. Must never be hardcoded to a different model. |
| input_tokens / output_tokens | Actual token counts from the API response. Estimates only as last resort. |
| router_decision_id | Links to a routing decision if one was made. Empty for direct Cecil work. |
| escalation_reason | Why this model was chosen if it was an escalation from a lower tier. |

### What each statusline percentage means

| Label | Definition |
|---|---|
| [Model] X% | Percentage of session tokens consumed by the main Claude Code session model |
| S:X% | Percentage of session tokens consumed by Sonnet-identified models (subagent entries with sonnet model_id, from custom sonnet-worker or statusline-setup agents) |
| H:X% | Percentage of session tokens consumed by Haiku-identified models (subagent entries with haiku model_id, from Explore built-in or custom haiku-worker agents — not misattributed general-purpose subagents) |
| Lq:X% | Percentage of session tokens consumed by qwen2.5 models via Ollama |
| Bq:X% | Percentage of session tokens consumed by qwen3:14b via Ollama |
| Qt:X% | Percentage of session tokens consumed by qt model via Ollama |

### Invariant

The sum of all percentages must account for 100% of logged tokens. No tokens may be double-counted (e.g., subagent tokens counted as both parent and Haiku). No tokens may be misattributed.

## 10. Operational Invariants

1. **Opus-only for authority/judgment.** Merge decisions, governance review, workfront selection, and user-facing synthesis must be performed by the Opus parent. These are never delegated.
2. **Non-Opus-class work must be routable.** If a subtask is classifiable as qwen-class (text processing, extraction, parsing) or haiku-class (file exploration, validation, bash execution), Cecil should delegate it. "Should" becomes "must" for the mandatory work classes defined in Section 7.
3. **No mislabeled model usage.** Every ledger entry must reflect the actual model that ran. Hardcoded model labels are prohibited.
4. **No claiming routed behavior that did not occur.** If Cecil executed a task directly, the ledger and report must say so. "No delegation" is an honest report. False delegation claims are not.
5. **No assuming state changed until written by authorized writer.** Routing decisions do not take effect until the subordinate invocation actually runs and returns.
6. **Subordinate output must be verifiable.** For untrusted tiers (qwen), output must be validated before use. For trusted tiers (Sonnet, Haiku), output is accepted but logged.
7. **Fallback is permitted but logged.** If a subordinate path fails, Cecil may handle the task directly, but must log the fallback with an escalation reason.

## 11. Verification Plan

### End-to-end verification scenario

A single test task that exercises the full routing path:

1. **Input:** A task containing both judgment-class and extraction-class subtasks (e.g., "Read the WORK_QUEUE.md and extract all TASK_IDs, then assess which are still relevant").
2. **Expected behavior:**
   - Cecil decomposes into subtasks
   - Extraction subtask routed to `ollama-call.sh` (qwen)
   - Judgment subtask handled by Cecil directly
   - Results synthesized by Cecil
3. **Verification evidence:**
   - Ledger contains at least one `provider=ollama` entry with the extraction task
   - Ledger contains at least one `provider=claude_code` entry for the session
   - Statusline shows non-zero Lq% or Bq%
   - Cecil's response includes synthesized results from both paths

### Claude subordinate verification (once custom agents are defined)

1. **Input:** A task requiring tool-capable execution below Opus tier (e.g., file exploration or structured validation).
2. **Expected behavior:**
   - Cecil identifies the subtask as Sonnet/Haiku-class
   - Invokes `Agent(subagent_type="sonnet-worker")` or `Agent(subagent_type="haiku-worker")`
   - Receives structured result
3. **Verification evidence:**
   - Ledger contains `provider=subagent` entry with correct model_id (sonnet or haiku)
   - Statusline shows non-zero S% or H%
   - No misattribution in ledger

### Attribution accuracy verification

1. Run a session that uses both Explore (Haiku) and general-purpose (Opus-inherit) subagents.
2. Verify ledger entries for Explore subagents show haiku model_id.
3. Verify ledger entries for general-purpose subagents show the parent model (opus), not `claude-haiku`.
4. Verify statusline H% reflects only actual Haiku usage (Explore + custom haiku-worker).

## 12. Ordered Implementation Lanes

### Lane 1: Truthing / Correction

Fix existing infrastructure so the ledger and statusline are honest.

| Task | File | Scope |
|---|---|---|
| Fix subagent model attribution | `system/scripts/log-subagent-usage.sh` | Change hardcoded `claude-haiku` to actual parent model |
| Fix statusline Haiku counting | `system/scripts/statusline.sh` | Remove `provider == "subagent"` from Haiku selector |
| Update operational-rules Cecil model | `system/operational-rules.json` | Reflect Opus 4.6 as current Cecil model |

**Depends on:** Nothing. Can start immediately.
**Acceptance:** Ledger entries from subagents show correct model. Statusline H% is 0 when no actual Haiku is used.

### Lane 2: Model-Pinned Agent Definitions

Create custom subagent definitions that enable Sonnet and Haiku as deliberate subordinate tiers.

| Task | File | Scope |
|---|---|---|
| Create `.claude/agents/` directory | `~/.claude/agents/` (user-level) or project-level | Directory creation |
| Create sonnet-worker agent definition | `~/.claude/agents/sonnet-worker.md` | Markdown file with `model: sonnet`, tools, system prompt |
| Create haiku-worker agent definition | `~/.claude/agents/haiku-worker.md` | Markdown file with `model: haiku`, tools, system prompt |
| Smoke-test both agents | Manual invocation | Verify `Agent(subagent_type="sonnet-worker")` and `Agent(subagent_type="haiku-worker")` return results |

**Depends on:** Lane 1 (so subagent usage is correctly attributed when agents are tested). No API key or external dependency required — Claude Code manages Claude API access internally.
**Acceptance:** Both custom agents respond when invoked via Agent tool. Ledger entries show correct model_id (sonnet/haiku). Statusline shows non-zero S% or H% respectively.

### Lane 3: Delegation Discipline Activation

Make Cecil actually use the existing and newly built invocation paths.

| Task | Scope |
|---|---|
| Define mandatory delegation work classes | Document which task types must be delegated |
| Exercise qwen delegation in a real task | Invoke `ollama-call.sh` from Cecil for an extraction subtask |
| Exercise Claude subordinate delegation (requires Lane 2) | Invoke `Agent(subagent_type="sonnet-worker")` or `Agent(subagent_type="haiku-worker")` from Cecil for a tool-capable subtask |

**Depends on:** Lane 1 (so delegation is correctly attributed). Lane 2 (for Claude subordinate delegation). Qwen delegation can start after Lane 1 only.
**Acceptance:** At least one real task shows delegation in the ledger. Statusline reflects non-zero subordinate usage.

### Lane 4: End-to-End Verification

Prove the full routing path works from task receipt to statusline display.

| Task | Scope |
|---|---|
| Run end-to-end verification scenario (Section 11) | Full path exercise |
| Run attribution accuracy verification | Confirm no misattribution |
| Document verification results | Record evidence of live routing |

**Depends on:** Lanes 1–3 complete.
**Acceptance:** Verification evidence from Section 11 is produced and recorded.

## 13. Recommended Execution Order

```
Lane 1: Truthing / Correction                ← START HERE
    │
    ├── Can begin immediately
    ├── No external dependencies
    └── Makes all subsequent work honest
    │
    ▼
Lane 2: Model-Pinned Agent Definitions       ← SECOND
    │
    ├── No external dependencies (no API key needed)
    ├── Small configuration task (2 markdown files)
    └── Enables Sonnet and Haiku as deliberate subordinate tiers
    │
    ▼
Lane 3: Delegation Discipline                ← THIRD
    │
    ├── Qwen delegation available after Lane 1
    ├── Claude subordinate delegation available after Lane 2
    └── Behavioral change, not script change
    │
    ▼
Lane 4: End-to-End Verification              ← LAST
    │
    └── Proves the system works
```

No lanes are blocked on external dependencies. All four lanes can proceed sequentially without waiting for API keys or external provisioning.

## 14. Risks and Failure Modes

### Risk 1: False attribution (MEDIUM)

Leaving the subagent misattribution unfixed while building new paths would compound the dishonesty. Lane 1 must complete before any new capability is added.

### Risk 2: Pseudo-routing (HIGH)

The highest risk is building the invocation paths but never actually using them — Cecil continues to execute everything directly, and the routing infrastructure remains ceremonial. Lane 3 (delegation discipline) is the mitigation. Without it, Lanes 1–2 are infrastructure without behavior change.

### Risk 3: Operator confusion (MEDIUM)

If the statusline shows percentages that don't match observed behavior, the operator loses trust in the display. Lane 1 corrections prevent this.

### Risk 4: Reporting/runtime divergence (HIGH)

This is the current state. The reporting surface (statusline, ledger, planning documents) describes a multi-model system. The runtime is single-model. This plan exists to close this exact divergence.

### Risk 5: Over-complexity (LOW)

The plan creates two agent definition files and corrects three existing files. No new scripts are needed for the Claude subordinate path. This is bounded. The risk is low if scope is held.

### Risk 6: Partial completion leaving the system dishonest (MEDIUM)

If only Lane 1 completes, the system is honest but not routed. If only Lane 2 completes without Lane 1, the system has new agents but still misattributes existing usage. The execution order (Lane 1 first) prevents the worst case.

## 15. Immediate Next Implementation Task Recommendation

**Lane 1, Task 1: Fix subagent model attribution and statusline Haiku counting.**

This is a single bounded task touching two files:
1. `system/scripts/log-subagent-usage.sh` — change hardcoded `claude-haiku` to correct model
2. `system/scripts/statusline.sh` — remove `provider == "subagent"` from Haiku selector

Acceptance criteria:
- Subagent ledger entries show correct parent model (not `claude-haiku`)
- Statusline H% is 0 when no actual Haiku was used
- Existing Lq%, Bq%, Qt% unaffected
- No other files changed

This task makes the existing system honest before any new capability is added.

**Second task (can follow immediately):** Update `operational-rules.json` to reflect Opus 4.6 as current Cecil model.

**Third task (Lane 2, can follow immediately after Lane 1):** Create `.claude/agents/` directory and add `sonnet-worker.md` and `haiku-worker.md` agent definitions. No external dependencies — Claude Code manages API access internally.
