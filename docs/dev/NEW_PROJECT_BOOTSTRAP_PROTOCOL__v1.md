# New Project Bootstrap Protocol v1

**Status:** Canonical protocol for bootstrapping new governed development projects from seed-chat content.
**Scope:** Development-process governance transplant only. No application-specific governance substrate.

## 1. Purpose and scope

### 1.1 What this protocol does

This protocol defines a reusable, operator-guided process for turning a seed chat (or any source of project-forming content) into a new governed development project with:

- a bound project identity
- transplanted development-process governance canon
- a verified operational baseline

The protocol covers the full lifecycle from seed identification through active-project status, including all intermediate artifacts, gates, and ownership boundaries.

### 1.2 What this protocol does not do

This protocol does not:

- transplant application-specific governance substrate (decision chains, capability registries, governed-action machinery, opacity metrics, verification state tracking, or approval stores)
- create cross-project coupling, registries, or automatic propagation mechanisms
- require the operator to remember prior bootstrap workflows (the process is self-guiding)
- replace or modify existing governance-layer canon

### 1.3 Development-process governance only

The protocol transplants development-process governance:

- role boundaries (operator, orchestrator, throughput engine, strategic lead)
- task discipline (specs before implementation, bounded autonomy)
- merge discipline (merge windows, conflict control, evidence)
- evidence expectations (deterministic proofs, test coverage)
- deterministic-first / judgment-second development discipline
- fail-closed process behavior

Application-specific governance (governed-action runtime, chain integrity, opacity metrics) is not part of the bootstrap. If a new project later needs application governance, that is a separate workfront after the project reaches ACTIVE status.

### 1.4 Independent-project assumption

Each bootstrapped project is operationally independent. There is no shared state, no cross-project triggers, and no registry of bootstrapped projects. Improvements to process canon may be manually propagated between projects at the operator's discretion, but there is no obligation or mechanism to do so.

### 1.5 Version-pinning assumption

When universal dev-process files are transplanted, they are pinned to the version that existed in the source repo at transplant time. Each file retains its own version identifier. There is no mechanism for automatic version tracking or upgrade notification across projects.

### 1.6 Universal unchanged file set

The following 8 files constitute the universal unchanged dev-process file set. These files are transplanted from the governance-layer repo to any newly bootstrapped project without modification. This table is the controlling source for Codex manifest extraction. Codex must not make universality judgments — this table is exhaustive.

| # | Canonical name | Source path (governance-layer) | Destination path (new project) | Transplant mode | Purpose | Version |
|---|---|---|---|---|---|---|
| 1 | OPS_PROCESS | `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | `docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | copy unchanged | Role definitions, collaboration loop, task/merge/evidence rules | v1 |
| 2 | AGENT_CONTRACT | `docs/dev/AGENT_CONTRACT.md` | `docs/dev/AGENT_CONTRACT.md` | copy unchanged | Agent confirmation policy and safe defaults | — |
| 3 | BRIEFING_FORMAT | `docs/dev/BRIEFING_FORMAT__BFPS_v12.md` | `docs/dev/BRIEFING_FORMAT__BFPS_v12.md` | copy unchanged | Session ingestion and handoff format | v12 |
| 4 | TASK_TEMPLATE | `docs/dev/TASK_TEMPLATE.md` | `docs/dev/TASK_TEMPLATE.md` | copy unchanged | Standard task specification template | — |
| 5 | INGESTION_WORKFLOW | `docs/dev/INGESTION_WORKFLOW.md` | `docs/dev/INGESTION_WORKFLOW.md` | copy unchanged | Workflow for ingesting external content | — |
| 6 | RUNBOOK | `docs/dev/RUNBOOK.md` | `docs/dev/RUNBOOK.md` | copy unchanged | Session-start protocol and lane definitions | — |
| 7 | haiku-worker | `.claude/agents/haiku-worker.md` | `.claude/agents/haiku-worker.md` | copy unchanged | Haiku-tier subordinate agent definition | — |
| 8 | sonnet-worker | `.claude/agents/sonnet-worker.md` | `.claude/agents/sonnet-worker.md` | copy unchanged | Sonnet-tier subordinate agent definition | — |

**Note on `.claude/commands/cecil.md`:** This file contains hardcoded repo-specific paths (repo root, filesystem locations) and Cecil operating constraints scoped to the specific project. It must be authored fresh per project by Cecil as a repo-local artifact. It is not in the universal set and must not be dispatched to Codex. Cecil authors this file directly in the destination repo, typically at Step 5b (alongside identity binding) or as a standalone correction step before Stage 6.

The universal set is 8 files, not 9. References to "9 universal files" elsewhere in this document and in activation test T5 should be read as 8.

### 1.7 Empty-directory sentinel convention

Git does not track empty directories. Bootstrap skeletons require directory structure to be present on pushed branches. The protocol-wide convention is:

- Place a `.gitkeep` file in any required directory that would otherwise be empty.
- `.gitkeep` files are zero-byte sentinel files. They contain no content.
- `.gitkeep` files may be removed once real content is added to the directory.
- Codex must use `.gitkeep` for all bootstrap-required empty directories without further judgment.

This convention applies to all bootstrap branches across all projects using this protocol.

### 1.8 Cross-repo source artifact copying rules

The Codex bootstrap dispatch may require files that originate in the governance-layer repo but must land in the destination repo (e.g., `system/scripts/activation-core.sh`, universal dev-process files). Codex operates in the destination repo and cannot read files from governance-layer at runtime.

The controlling rules are:

1. **Universal files (section 1.6):** The dispatch must include the full governance-layer source path for each file. The dispatch author (ChatGPT) must verify that each source file exists on governance-layer `origin/main` before including it.
2. **Cross-repo scripts:** Any script that must be present in the destination repo (e.g., `activation-core.sh`) must be listed in the dispatch with its governance-layer source path and destination path. The dispatch must instruct Codex to copy the file from governance-layer to the destination repo.
3. **Source availability gate:** If a required source file does not exist on governance-layer `origin/main`, the dispatch must not be issued. The missing file is a blocking precondition, not something Codex should work around.
4. **Codex cannot discover sources:** The dispatch must never instruct Codex to "find" or "locate" a file across repos. Every cross-repo source must be an explicit path.

## 2. Context model

The protocol distinguishes three contexts. These contexts may be in different ChatGPT projects, different terminal sessions, or different repos.

### 2.1 Source context

The project or chat where the operator identifies seed material. This can be any ChatGPT project, any chat, any document, or any other source. The protocol does not assume the source context is the destination. The source context is read-only — the protocol extracts from it but does not modify it.

### 2.2 Bootstrap control context

The new working chat in the destination GPT project. This is where ChatGPT orchestrates the bootstrap process: producing the Seed Package, performing preliminary screening, generating dispatches. The bootstrap control context is created by the operator at Stage 1.

### 2.3 Destination project context

The GPT project and repo that will become the new governed project. The GPT project is created at Stage 1. The repo is created at Stage 5. Before Stage 5, bootstrap artifacts are chat-level (pre-repo). After Stage 5, bootstrap artifacts include repo-level files (post-repo).

## 3. Lifecycle

The lifecycle has 10 explicit stages. Each stage has a defined context, actor, action, output, and gate.

### Stage 0: Portable initiation

| | |
|---|---|
| **Context** | Any project / any chat (source context) |
| **Actor** | Operator (Greg) |
| **Action** | Operator identifies seed material worth extracting into a project. Operator copies or exports the relevant seed content. |
| **Output** | Raw seed content in operator's clipboard or a document. |
| **Gate** | Operator's judgment that the content crosses the implementation-intent threshold: the seed contains at least one concrete thing to build, not just discussion or exploration. |

The operator does not need to remember the protocol details at this stage. The PORTABLE INITIATION INSTRUCTIONS reference document provides the step-by-step sequence.

### Stage 1: Destination project setup

| | |
|---|---|
| **Context** | ChatGPT platform (project management UI) |
| **Actor** | Operator |
| **Action** | Operator creates a new GPT project with a working name. Operator creates a new working chat inside that project. Operator pastes the DESTINATION WORKING-CHAT START BLOCK into the new chat. |
| **Output** | A new GPT project and working chat with bootstrap context loaded. |
| **Gate** | The working chat acknowledges the start block and is ready for seed intake. |

The start block establishes bootstrap mode. It tells ChatGPT the protocol version, the project working name, and that the next input will be seed content. ChatGPT will automatically produce a Seed Package when seed content is provided — no separate intake instructions are required.

### Stage 2: Seed intake

| | |
|---|---|
| **Context** | Destination working chat (bootstrap control context) |
| **Actor** | Operator → ChatGPT |
| **Action** | Operator pastes seed content into the working chat. ChatGPT processes the seed content and produces a Seed Package. |
| **Output** | Structured Seed Package (chat-level artifact, not a file). |
| **Gate** | ChatGPT confirms the Seed Package is complete and presents it for operator review. |

If seed content is provided in multiple chunks, ChatGPT accumulates and asks whether more is coming before finalizing the package.

If the operator wants to provide notes or constraints that are not part of the seed content, the operator prefixes them with `OPERATOR NOTES:` and ChatGPT routes them to the `operator_notes` field.

### Stage 3: Preliminary screening

| | |
|---|---|
| **Context** | Destination working chat |
| **Actor** | ChatGPT |
| **Action** | ChatGPT evaluates the Seed Package against the preliminary screening criteria (section 7). This is a structural completeness check, not a promotability judgment. |
| **Output** | If no obvious deficiencies: CECIL EVALUATION DISPATCH containing the Seed Package and screening notes. If obvious deficiencies: PRELIMINARY DEFICIENCY REPORT with repair guidance. |
| **Gate** | Preliminary screen pass/fail. Pass forwards to Cecil. Fail enters repair loop with operator. |

ChatGPT screening catches obvious gaps: missing scope, no concrete tasks, no nameable deliverable. It does not judge whether the seed is architecturally sound or whether first-pass canon can be authored without major invention. That judgment belongs to Cecil at Stage 4.

A seed that passes preliminary screening may still be rejected or revised by Cecil.

### Stage 4: Cecil promotability evaluation

| | |
|---|---|
| **Context** | Cecil session (governance-layer repo or any Cecil-capable context) |
| **Actor** | Operator → Cecil |
| **Action** | Operator pastes the Cecil evaluation dispatch to Cecil. Cecil evaluates the Seed Package for promotability: Can first-pass canon be authored without major invention? Are scope boundaries clear enough for bounded task generation? Are there blocking ambiguities requiring operator clarification? |
| **Output** | Cecil promotability verdict: PROMOTE / REVISE / REJECT. If PROMOTE: Cecil produces an APPROVED BOOTSTRAP PLAN. |
| **Gate** | Cecil verdict. REVISE returns to Stage 2/3 with specific deficiencies. REJECT halts the bootstrap with stated reasons. |

Cecil is the sole promotability authority. No other actor may promote a seed to bootstrap.

### Stage 5: Repo creation and identity binding

This stage has two steps with distinct ownership.

#### Step 5a: Operator platform precondition

| | |
|---|---|
| **Context** | GitHub platform / local filesystem |
| **Actor** | Operator |
| **Action** | Operator creates the GitHub repo. Operator confirms the repo URL and local clone path to Cecil. |
| **Output** | Empty repo exists. Operator provides `repo_remote` and `repo_root`. |
| **Gate** | Repo exists and is accessible. |

This is a platform action only the operator can perform (GitHub account ownership, filesystem location choice). It is not protocol work.

#### Step 5b: Cecil identity binding

| | |
|---|---|
| **Context** | Repo terminal |
| **Actor** | Cecil |
| **Action** | Cecil creates PROJECT_IDENTITY.md from the approved bootstrap plan. Cecil commits it as the repo root commit. Cecil pushes to the remote. |
| **Output** | Repo has a root commit containing project identity. |
| **Gate** | Root commit exists, PROJECT_IDENTITY.md contains all binding fields (section 8), remote is in sync. |

**This is the pre-repo to post-repo boundary.** Before this step, all bootstrap artifacts are chat-level. After this step, bootstrap artifacts include repo files.

### Stage 6: Codex mechanical bootstrap

| | |
|---|---|
| **Context** | Destination working chat → Codex |
| **Actor** | ChatGPT → Codex (dispatched by ChatGPT, run by operator) |
| **Action** | ChatGPT produces a CODEX BOOTSTRAP DISPATCH from the approved plan. Codex creates a bootstrap branch, copies universal dev-process files unchanged, authors repo-local stubs from templates, and creates `.claude/` configuration. |
| **Output** | Bootstrap branch with full dev-process canon skeleton. |
| **Gate** | Branch exists, all expected files present, no application-governance substrate included. |

Codex operates against the base SHA of the identity-binding root commit. The dispatch includes explicit file creation allowlists and a "do not create" list excluding application governance substrate.

### Stage 7: Core activation

| | |
|---|---|
| **Context** | Cecil session in the new repo |
| **Actor** | Cecil |
| **Action** | Cecil merges the bootstrap branch to main. Cecil runs the core activation test suite (section 9.1). |
| **Output** | Main branch with full dev-process canon. Core activation test results. |
| **Gate** | All core activation tests pass. |

If core activation passes, project status transitions to **BOOTSTRAPPED**.

BOOTSTRAPPED means the repo installation is proven correct. It does not mean the operational process has been proven.

### Stage 7b: Operational activation

| | |
|---|---|
| **Context** | Destination working chat → Codex → Cecil |
| **Actor** | ChatGPT, Codex, Cecil (full actor set) |
| **Action** | ChatGPT produces a minimal real task dispatch. Operator runs it in Codex. Cecil merges the result. Cecil verifies evidence landed correctly. |
| **Output** | One completed task cycle with evidence. |
| **Gate** | All operational activation tests pass (section 9.2). |

If operational activation passes, project status transitions to **ACTIVE**.

Stage 7b may happen immediately after Stage 7 or may be deferred if Codex capacity is not immediately available. BOOTSTRAPPED is a valid holding state.

### Stage 8: Active project state

| | |
|---|---|
| **Context** | Destination project (all contexts) |
| **Actor** | All (operator, ChatGPT, Codex, Cecil) |
| **Action** | Normal operating model begins (standard dispatch / build / merge cycle per OPS_PROCESS). Seed content migration (if implementation artifacts exist in the seed) proceeds through the now-operational governed process. |
| **Output** | First real task dispatches through the standard process. |
| **Gate** | At least one real task cycle completes successfully. |

## 4. Authority model

### 4.1 Operator (Greg)

The operator is the source of intent, platform preconditions, and acceptance.

Operator-owned actions:
- Identify seed material and judge implementation-intent threshold (Stage 0)
- Create the GPT project and working chat (Stage 1)
- Paste seed content and operator notes (Stage 2)
- Review Seed Packages and screening results (Stage 3)
- Paste dispatches to Cecil and Codex (Stages 4, 6)
- Create the GitHub repo and provide repo URL / path (Stage 5a)
- Run Codex dispatches (Stage 6)
- Approve status transitions

### 4.2 ChatGPT

ChatGPT is the orchestrator and seed processor.

ChatGPT-owned actions:
- Produce Seed Packages from raw seed content (Stage 2)
- Perform preliminary screening against structural criteria (Stage 3)
- Generate Cecil evaluation dispatches (Stage 3)
- Generate Codex bootstrap dispatches from approved plans (Stage 6)
- Generate post-repo activation blocks (Stage 7b)

ChatGPT does not:
- Judge promotability (that is Cecil's authority)
- Author canon or template artifacts (that is Cecil's authority)
- Make architectural decisions about the new project

### 4.3 Cecil

Cecil is the strategic authority, sole promotability gate, and canon owner.

Cecil-owned actions:
- Evaluate seed promotability (Stage 4) — sole authority
- Produce approved bootstrap plans (Stage 4)
- Author PROJECT_IDENTITY.md and commit it as root (Stage 5b)
- Merge bootstrap branches to main (Stage 7)
- Run activation test suites (Stages 7, 7b)
- Accept or reject activation results
- Own all canon and template artifacts

### 4.4 Codex

Codex is the bounded mechanical executor.

Codex-owned actions:
- Copy universal dev-process files unchanged
- Author repo-local stubs from templates
- Create `.claude/` configuration
- Execute within explicit allowlists

Codex preconditions:
- May not begin until Cecil-owned canon and template artifacts exist on main
- Must operate within allowlists defined in the Codex bootstrap dispatch
- Must not create application-governance substrate
- Must not modify canon or template artifacts

## 5. Artifact model

The protocol uses 7 canonical artifact types. Repo copies of templates are the canonical source. Pasted blocks are runtime instances of those templates.

### 5.1 PORTABLE INITIATION INSTRUCTIONS

A reference document the operator keeps accessible (personal project, bookmarked note, governance-layer repo).

| | |
|---|---|
| **Created by** | Cecil (one-time authoring) |
| **Consumed by** | Operator |
| **When** | Stage 0 |
| **Pre-repo or post-repo** | Pre-repo |
| **Project-creation record** | No (reference artifact, not per-project) |

Contents: Step-by-step instructions telling the operator what to do when seed material is identified. Written so the operator can follow it without remembering prior bootstraps.

### 5.2 DESTINATION WORKING-CHAT START BLOCK

A paste block that initializes the bootstrap control chat.

| | |
|---|---|
| **Created by** | Cecil (template); operator pastes it |
| **Consumed by** | ChatGPT (in the new working chat) |
| **When** | Stage 1 |
| **Pre-repo or post-repo** | Pre-repo |
| **Project-creation record** | Yes |

Contents: Protocol version, project working name, bootstrap-mode instructions for ChatGPT, statement that seed content should be processed into a Seed Package automatically.

### 5.3 SEED PACKAGE

A structured artifact produced by ChatGPT from raw seed content. See section 6 for full specification.

| | |
|---|---|
| **Created by** | ChatGPT |
| **Consumed by** | Operator (review), Cecil (evaluation) |
| **When** | Stage 2 output |
| **Pre-repo or post-repo** | Pre-repo |
| **Project-creation record** | Yes (canonical record of what was extracted from the seed) |

### 5.4 CECIL EVALUATION DISPATCH

A dispatch block ChatGPT produces for Cecil to evaluate the Seed Package.

| | |
|---|---|
| **Created by** | ChatGPT |
| **Consumed by** | Cecil (via operator paste) |
| **When** | Stage 3 output (if screening passes) |
| **Pre-repo or post-repo** | Pre-repo |
| **Project-creation record** | Yes |

Contents: The Seed Package (with source excerpts intact), ChatGPT's preliminary screening result, flags or concerns, explicit statement that promotability evaluation is Cecil's authority.

### 5.5 APPROVED BOOTSTRAP PLAN

Cecil's output from the promotability evaluation.

| | |
|---|---|
| **Created by** | Cecil |
| **Consumed by** | ChatGPT (to produce Codex dispatch), operator (approval) |
| **When** | Stage 4 output (if PROMOTE) |
| **Pre-repo or post-repo** | Pre-repo (plan exists before repo) |
| **Project-creation record** | Yes |

Contents: Finalized project identity binding fields, repo name, directory structure, universal file manifest, repo-local file list with stub guidance, project-specific constraints or deviations, activation test suite parameters.

### 5.6 CODEX BOOTSTRAP DISPATCH

A standard Codex dispatch for mechanical repo skeleton creation.

| | |
|---|---|
| **Created by** | ChatGPT (from the approved bootstrap plan) |
| **Consumed by** | Codex |
| **When** | Stage 6 |
| **Pre-repo or post-repo** | Post-repo (repo must have identity commit) |
| **Project-creation record** | Yes |

Contents: Base SHA (identity-binding root commit), file creation allowlist (universal files + repo-local stubs), explicit "do not create" list (no application governance substrate), branch name, evidence requirements.

**Handoff grounding rule:** The Codex bootstrap dispatch must be self-contained. Codex cannot read the Approved Bootstrap Plan or any prior chat-level artifact. Every value Codex needs — directory structure, file paths, stub content guidance, project identity fields, universal file source paths — must be explicitly present in the dispatch body. A dispatch that says "per the Approved Bootstrap Plan" without inlining the relevant details will cause Codex to fail closed.

### 5.7 POST-REPO ACTIVATION BLOCK

Instructions for Cecil to merge the bootstrap branch and run activation tests.

| | |
|---|---|
| **Created by** | ChatGPT |
| **Consumed by** | Cecil |
| **When** | Stage 7 |
| **Pre-repo or post-repo** | Post-repo |
| **Project-creation record** | Yes (activation test results are the project birth certificate) |

Contents: Merge dispatch for bootstrap branch, activation test suite invocation, expected pass criteria, status transition instructions.

## 6. Seed Package specification

### 6.1 Structure

```
SEED PACKAGE v{N}
Protocol: NEW_PROJECT_BOOTSTRAP_PROTOCOL v1
Timestamp: {ISO 8601 UTC}
Prior version: {v{N-1} or "none"}

--- STRUCTURED EXTRACTION ---

project_name:           {string — valid repo name candidate}
scope_statement:        {1-3 sentences}
deliverable_type:       {library | service | tool | spec_corpus | mixed}
primary_language:       {string or "tbd"}
key_constraints:
  - {constraint}
initial_task_candidates:
  - title: {string}
    scope: {one sentence}
    deliverable: {code | spec | test | config}
source_reference:       {human-readable source chat/doc reference}
governed_families:      {list or "none"}
external_dependencies:  {list or "none"}
operator_notes:         {string or "none"}
architectural_decisions:
  - decision: {string}
    rationale: {string}

preliminary_screening:
  structural_completeness: {pass | fail}
  deficiencies: []
  flags_for_cecil: []

--- SOURCE EXCERPTS ---

{Preserved source material bearing on ambiguity, instability,
 or contested decisions. Each excerpt is labeled.}

-- excerpt: {label} --
why_preserved: {rationale}
source_content: |
  {verbatim excerpt from seed content}
--

--- IMPLEMENTATION SKETCHES ---

{Optional. Only if the seed contained code or pseudocode worth preserving.}

-- sketch: {label} --
{content}
--
```

### 6.2 Required fields

| Field | Type | Description |
|---|---|---|
| `project_name` | string | Working name for the project. Must be a valid repo name candidate. |
| `scope_statement` | string | What the project does and does not do. 1-3 sentences. |
| `deliverable_type` | enum | `library`, `service`, `tool`, `spec_corpus`, or `mixed` |
| `primary_language` | string | Primary implementation language, or `mixed` / `tbd` |
| `key_constraints` | list | Architectural or process constraints identified in the seed |
| `initial_task_candidates` | list | At least 1 concrete task. Each has `title`, `scope` (one sentence), `deliverable` type. |
| `source_reference` | string | Human-readable reference to the source chat or document |
| `extraction_timestamp` | string | ISO 8601 UTC |
| `preliminary_screening` | object | ChatGPT's structural completeness check result |

### 6.3 Optional fields

| Field | Type | Description |
|---|---|---|
| `governed_families` | list | Only if the project will use governed-action patterns |
| `external_dependencies` | list | Known external systems or services |
| `operator_notes` | string | Operator context not present in the seed |
| `architectural_decisions` | list | Decisions already made: `{decision, rationale}` |
| `implementation_sketches` | list | Code or pseudocode fragments: `{label, content}` |

### 6.4 Source-excerpt preservation rules

1. Ambiguity-bearing material must be preserved. If the seed contains competing approaches, unresolved questions, or statements that could be interpreted multiple ways, the relevant passages go in SOURCE EXCERPTS with a `why_preserved` label.
2. Instability-bearing material must be preserved. If the seed contains ideas that were proposed and partially walked back, or constraints stated tentatively, those passages are preserved.
3. Resolved material may be distilled. If the seed clearly resolved a question, ChatGPT may distill it into the structured extraction without preserving the deliberation.
4. When in doubt, preserve. ChatGPT should err toward preserving excerpts. Cecil can ignore irrelevant excerpts but cannot evaluate discarded material.
5. Source excerpts are not the full seed. ChatGPT selects passages bearing on evaluation-relevant ambiguity. Routine conversational content is not preserved.

### 6.5 Size bounds

| Element | Maximum |
|---|---|
| `initial_task_candidates` | 10 entries. Overflow deferred to post-activation backlog. |
| `source_excerpts` | 10 excerpts, each approximately 500 words. Consolidate related excerpts and note consolidation. |
| `implementation_sketches` | 5 sketches, each approximately 200 lines. |

The total Seed Package should remain readable in a single pass. If it cannot, the seed is likely too large or too ambiguous for promotion and should be flagged.

### 6.6 Large or multi-part seeds

If seed content exceeds what can be processed in a single pass, the operator provides it in labeled chunks (e.g., "Seed Part 1 of 3"). ChatGPT processes each chunk incrementally, building up the Seed Package across chunks. ChatGPT prioritizes in this order: scope statement, constraints, task candidates, architectural decisions, implementation sketches.

### 6.7 Versioning model

- First package: `SEED PACKAGE v1` with `Prior version: none`.
- After repair: `SEED PACKAGE v2` with `Prior version: v1`.
- Prior versions are retained in chat history. They are not deleted or overwritten.
- The CECIL EVALUATION DISPATCH carries the latest version and states the version number and how many prior versions exist.
- Cecil may request a prior version. The operator can scroll up and paste it, or ChatGPT can reproduce it from chat history.

Deficiency reports follow the same numbering:

```
PRELIMINARY DEFICIENCY REPORT v1
Evaluating: SEED PACKAGE v1
...

SEED PACKAGE v2
Prior version: v1
Addressing: PRELIMINARY DEFICIENCY REPORT v1
...
```

## 7. Preliminary screening model

### 7.1 Scope of preliminary screening

ChatGPT performs preliminary screening as a structural completeness check. This is not authoritative promotability judgment. A seed that passes preliminary screening may still be rejected or revised by Cecil at Stage 4.

Preliminary screening catches obvious structural gaps. It does not evaluate architectural soundness, canon-authoring feasibility, or scope stability.

### 7.2 Screening criteria

All of the following must be met for a preliminary screen pass:

1. **Implementation intent**: The seed contains at least one concrete thing to build, not just discussion or exploration.
2. **Scope boundary**: The project scope can be stated in 1-3 sentences without requiring further research or design.
3. **Deliverable clarity**: The primary deliverable type is identifiable.
4. **Task concreteness**: At least one initial task candidate can be written with a title, scope sentence, and deliverable type.
5. **Constraint legibility**: Key constraints are explicitly stated or clearly derivable. The project does not require discovering its own constraints through exploratory implementation.
6. **Naming viability**: A project name and repo name candidate can be derived without ambiguity.

### 7.3 Preliminary deficiency reporting

If any criterion is not met, ChatGPT produces a PRELIMINARY DEFICIENCY REPORT:

```
PRELIMINARY DEFICIENCY REPORT v{N}
Evaluating: SEED PACKAGE v{M}

SCREENING RESULT: FAIL

DEFICIENCIES:
- [criterion number]: [specific deficiency description]

REPAIR GUIDANCE:
- [for each deficiency]: [what the operator must provide or clarify]

NEXT STEP:
After addressing the listed deficiencies, provide the missing information
or re-paste repaired seed content. ChatGPT will update the Seed Package
and re-screen.
```

### 7.4 Rerun model

- Operator provides additional information or clarification.
- ChatGPT updates the Seed Package as a new version (incremental update, not restart).
- ChatGPT re-screens against the same criteria.
- The updated Seed Package references its prior version. The repair trail remains legible.
- There is no limit on re-screening attempts.

## 8. Project identity and binding schema

### 8.1 Minimum binding fields

| Field | Description | Set when |
|---|---|---|
| `project_name` | Canonical project name (also the repo name) | Stage 2 (Seed Package) |
| `project_scope` | 1-3 sentence scope statement | Stage 2 (Seed Package) |
| `governing_operator` | Operator identity for this project | Stage 4 (Cecil evaluation) |
| `bootstrap_protocol_version` | Version of this protocol | Stage 1 (start block) |
| `bootstrap_timestamp_utc` | When bootstrap was initiated | Stage 1 (start block) |
| `repo_root` | Canonical filesystem path to the repo root | Stage 5 (repo creation) |
| `repo_remote` | GitHub remote URL | Stage 5 (repo creation) |
| `seed_source_reference` | Human-readable reference to seed source | Stage 2 (Seed Package) |

### 8.2 Where identity appears

| Context | Identity fields present |
|---|---|
| Destination working-chat start block | `project_name`, `bootstrap_protocol_version`, `bootstrap_timestamp_utc` |
| Seed Package | `project_name`, `scope_statement`, `source_reference` |
| Approved Bootstrap Plan | All pre-repo fields + planned `repo_root`, `repo_remote` |
| PROJECT_IDENTITY.md (repo file) | All fields |
| Codex dispatches | `project_name`, `repo_root`, `repo_remote` |
| Codex completion packets | `project_name`, `repo_remote` |
| Cecil merge reports | `project_name` |

### 8.3 PROJECT_IDENTITY.md

PROJECT_IDENTITY.md is the repo-canonical identity binding file. It is created by Cecil as the first commit at Step 5b and is never modified after creation.

```markdown
# Project Identity

| Field | Value |
|---|---|
| project_name | {value} |
| project_scope | {value} |
| governing_operator | {value} |
| bootstrap_protocol_version | {value} |
| bootstrap_timestamp_utc | {value} |
| repo_root | {value} |
| repo_remote | {value} |
| seed_source_reference | {value} |
```

## 9. Activation model

### 9.1 Core activation

Core activation proves the repo installation is correct. It is run by Cecil at Stage 7, immediately after merging the bootstrap branch. All tests are mechanical and scriptable.

| Test | Proves |
|---|---|
| T1: PROJECT_IDENTITY.md exists, all required fields non-empty | Identity binding present |
| T2: `project_name` matches repo directory name | Identity consistent with repo |
| T3: Repo is git, remote matches `repo_remote` in identity file | Repo binding correct |
| T4: Main branch has at least 2 commits (identity + bootstrap) | Bootstrap branch merged |
| T5: All 8 universal dev-process files exist and are non-empty (per section 1.6) | Canon transplant completed |
| T6: OPS_CANONICAL.md exists and contains `project_name` | Repo-local canon stub present |
| T7: `.claude/settings.json` exists and is valid JSON | Agent configuration present |
| T8: WORK_QUEUE.md exists | Task tracking surface present |

**Pass rule:** All 8 tests pass. Status transitions to **BOOTSTRAPPED**.

**Fail rule:** Any failure blocks BOOTSTRAPPED. Output identifies the specific test and the missing or incorrect value.

Core activation tests should be delivered as a shell script (`system/scripts/activation-core.sh`) included in the bootstrap branch.

### 9.2 Operational activation

Operational activation proves the governed development process works end-to-end. It is run at Stage 7b and requires actual multi-agent dispatch cycles.

| Test | Proves |
|---|---|
| T9: A minimal task dispatch generated with correct project identity headers | Task generation works |
| T10: Codex completion returns with correct project identity | Codex binding correct |
| T11: Branch created following naming convention | Branch discipline works |
| T12: Cecil merges result without error | Merge discipline works |
| T13: Evidence artifacts land at expected paths | Evidence contract works |

**Pass rule:** All 5 tests pass. Status transitions to **ACTIVE**.

**Fail rule:** Any failure blocks ACTIVE. Project remains BOOTSTRAPPED. Output identifies the specific test.

**Evidence-type flexibility:** The operational activation task is not required to produce code. Spec authoring, canon authoring, or any other governed deliverable type satisfies T9-T13 as long as: (a) a task dispatch was generated, (b) Codex produced a completion on a correctly-named branch, (c) Cecil merged the result, and (d) deliverable artifacts landed at paths consistent with the project's directory structure. "Evidence artifacts" in T13 means whatever the task's deliverable type produces (specs, code, config, tests), not exclusively code or test output.

### 9.3 Status transitions

```
(no project)
  → Stage 5 complete → repo exists (no formal status)
  → Stage 7 core activation passes → BOOTSTRAPPED
  → Stage 7b operational activation passes → ACTIVE
```

**BOOTSTRAPPED** is a valid holding state. A project may remain BOOTSTRAPPED indefinitely if operational activation is deferred. It means: the repo is correctly installed and dev-process canon is in place, but a live dispatch/merge cycle has not been proven.

**ACTIVE** means: the project has completed at least one full governed task cycle and is operationally live.

There is no path from BOOTSTRAPPED to ACTIVE without completing operational activation. There is no shortcut.

**Status-surface rules:**

- Status transitions are declared by Cecil in the merge report or activation report that completes the relevant gate.
- The canonical status surface is `docs/dev/OPS_CANONICAL.md` in the destination repo. Cecil updates the project status field in OPS_CANONICAL.md when a transition occurs.
- If OPS_CANONICAL.md does not yet have a `project_status` field, Cecil adds one at the time of the first status transition (BOOTSTRAPPED).
- Status is not written to PROJECT_IDENTITY.md (which is immutable after creation).
- Status is not written to WORK_QUEUE.md (which tracks tasks, not project lifecycle).

## 10. Gates and completion standard

### 10.1 Gate: Cecil canon must exist before Codex participates

Codex may not begin bootstrap work until:
- The master protocol document exists as repo canon on main in the governance-layer repo.
- All 5 pre-repo template artifacts exist as repo canon on main in the governance-layer repo.

### 10.2 Gate: Codex mechanical assembly must complete before pilot

A pilot may not begin until:
- The universal file manifest exists.
- Repo-local stub templates exist.
- The core activation test script exists and passes against a mock skeleton.

### 10.3 Completion standard

The protocol is genuinely implemented when all of the following are true:

1. The master protocol document exists as repo canon on main.
2. All 5 pre-repo template artifacts exist as repo canon on main.
3. The universal file manifest exists as repo canon on main.
4. Repo-local stub templates exist as repo canon on main.
5. The core activation test script exists and passes against a mock skeleton.
6. At least one real project has been bootstrapped to ACTIVE status using the protocol.

Items 1-5 are necessary but not sufficient. Item 6 is the completion proof. A protocol that has never been run is a spec, not an implementation. The pilot is not optional.
