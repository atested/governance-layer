# External AI Review System for Development Design Corpus — v0

## 1. System Overview

### 1.1 What this system is

A structured program for obtaining serious external AI evaluation of a multi-agent development system — the process documents, contracts, scripts, templates, and workflow infrastructure that govern how this project is built.

This is not a review of the product the system builds. It is a review of the *development system* itself — how work is specified, dispatched, executed, verified, and merged by a team of human and AI actors.

### 1.2 Why this exists

The development system has grown organically through real operational pressure. It now includes ~25,000 lines of process documentation, ~4,500 lines of operational scripts, 100+ task specs, and a multi-agent collaboration model spanning four actors (Greg, ChatGPT, Codex, Cecil). No single participant has a complete external view of whether the system is well-matched to its task, internally consistent, or efficiently structured.

External review addresses this by providing independent evaluation unconstrained by the project's internal momentum.

### 1.3 Design principles

**Evaluation, not audit.** The review should surface what is strong alongside what is weak. Pure defect-hunting misses the design choices that are working well and should be preserved.

**Structured enough to compare, flexible enough to discover.** Multiple independent reviewers must produce outputs that can be meaningfully compared without constraining them so tightly that they cannot surface unexpected insights.

**Grounded, not impressionistic.** Every finding — positive or negative — must reference specific artifacts. "The process feels heavy" is not useful. "OPS_PROCESS v1 §9.1 requires 5 structured fields per dispatch that duplicate information already in the task spec" is useful.

**Proportional justification.** Small fixes need light reasoning. Larger changes need correspondingly stronger evidence and justification. This scales continuously, not as a binary gate.

## 2. Corpus Definition

### 2.1 What goes in the corpus

The review corpus contains the development design artifacts organized into four tiers by review priority.

**Tier 1 — Core Process (must review)**

These define the development system's operating model:

| Artifact | Purpose |
|---|---|
| `OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md` | Multi-agent collaboration process, roles, merge strategy |
| `AGENT_CONTRACT.md` | Cecil operating contract, confirmation policy, safe defaults |
| `CODEX_CAPABILITY_TIER__v0.md` | Codex role, boundaries, QT-first delegation, escalation rules |
| `MERGE_GATE.md` | Merge checklist, fail-closed rules, evidence requirements |
| `EVIDENCE-CONTRACT.md` | Evidence bundle specification |
| `TASK_TEMPLATE.md` | Standard task specification format |
| `OPS_CANONICAL.md` | Operational invariants and script registry |
| `RUNBOOK.md` | Operational procedures manual |
| `DISPATCH_LIBRARY__CECIL_CODEX__v10.md` | Dispatch templates |
| `BRIEFING_FORMAT__BFPS_v12.md` | Briefing format specification |

**Tier 2 — Operational Scripts (must review)**

These implement the development process:

| Artifact | Purpose |
|---|---|
| `system/scripts/codex-unattended.sh` | Codex execution envelope: preflight, branch, allowed-files, evidence, reception checks, completion packets |
| `system/scripts/qt-runner.sh` | QT verification runner |
| `system/scripts/qt-usage-summary.sh` | QT observability |
| `system/scripts/release-gate.sh` | Release gate and proof-bundle generation |
| `system/scripts/validate-proof-bundle.sh` | Proof-bundle validation |
| `system/scripts/codex-batch.sh` | Batch generation |
| `system/ops/limits.json` | Execution caps |

**Tier 3 — Design Context (should review)**

These provide context for evaluating Tier 1-2 artifacts:

| Artifact | Purpose |
|---|---|
| `INGESTION_WORKFLOW.md` | End-to-end task lifecycle |
| `TASK_SEEDS.md` | Task generation system |
| `WORK_QUEUE.md` | Current task state |
| `ASSIGNMENTS.md` | Task ownership history |
| `QT_JOB_SCHEMA.md` | QT job format |
| `CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` | Reception validation spec |
| 5 representative READY task specs | Concrete examples of task specification |
| `ROUTED_RUNTIME_BASELINE__COMPLETION_RECORD__v0.md` | Cecil routed-runtime baseline proof |
| `CODEX_ROUTED_RUNTIME_BASELINE__COMPLETION_RECORD__v0.md` | Codex baseline proof |
| `QT_RUNTIME_PROOF__v0.md` | QT liveness proof |

**Tier 4 — Domain Context (may review)**

These help the reviewer understand what the development system is building:

| Artifact | Purpose |
|---|---|
| `docs/SCOPE.md` | What the governance layer is and is not |
| `docs/POLICY.md` | Policy rules |
| `docs/GOVERNANCE_OVERVIEW.md` | System guarantees and architecture |
| `docs/THREAT-MODEL.md` | Threat model |
| `docs/DECISION-RECORD.md` | Decision record schema |
| `RESIDUAL_DISCRETION_DOCTRINE.md` | RDD architecture |

### 2.2 What stays out

- Individual task evidence bundles (`docs/dev/evidence/TASK_###/`)
- Chat records (`docs/dev/chat-records/`)
- Implementation source code (`scripts/policy-eval.py`, `mcp/server.py`, etc.)
- Git history (reviewer gets artifacts as-is, not commit-by-commit)
- Operational logs (`system/logs/`)
- Personal/system configuration (`.claude/settings.json`, etc.)

### 2.3 Corpus size target

The corpus should be large enough to evaluate the system and small enough for a single review session. Target: 20-35 files, ~8,000-15,000 lines. The tier system enables this — Tier 1+2 is ~15 files and forms the mandatory core. Tiers 3-4 are included as context but the reviewer is told the core evaluation targets are Tier 1-2.

## 3. Context Framing Document

### 3.1 Purpose

The reviewer must not encounter disconnected files. The corpus package includes a **Context Framing Document** that gives the reviewer enough understanding to critique the system fairly. This document is the first thing the reviewer reads.

### 3.2 Required content

The context framing document must contain these sections, in this order:

**A. What this project is.** A brief factual description of what the project builds, sourced from `docs/SCOPE.md`. Enough for the reviewer to understand the domain without becoming a domain expert. Two to four sentences.

**B. What the development design is.** Not the product itself, but the process, contracts, templates, and scripts that govern how the product is built. The review target is the development system, not the product.

**C. Why the development system exists.** The project is built by a multi-agent team (human operator, AI orchestrator, AI execution engine, AI merge authority) operating under capacity constraints, weekly budget resets, and the need for concurrent branch-safe execution. The development system exists to make this collaboration reliable, auditable, and bounded.

**D. The four actors and their roles.** Greg (direction, acceptance), ChatGPT (orchestration, dispatch), Codex (bounded execution), Cecil (governance, merge authority, strategy). Why duties are split this way: different trust levels, different capability profiles, different budget constraints, and the need for fail-closed separation of concerns.

**E. What good performance looks like.** High task throughput with low merge conflict rate. Truthful reporting. Bounded autonomy — each actor works within explicit constraints. Fail-closed behavior on ambiguity. Evidence-backed completion claims. Clean merge history.

**F. Current system maturity.** Factual maturity indicators: number of tasks executed, branches merged, baseline completions achieved. The system is past initial setup and into production-level operation, but still evolving. Source from `ASSIGNMENTS.md` history count and completion records.

**G. Known tensions.** The development system serves competing goals: throughput vs. safety, autonomy vs. oversight, specification rigor vs. dispatch speed, documentation completeness vs. document maintenance cost. The reviewer should evaluate how well the system navigates these tensions, not assume one goal dominates.

### 3.3 What the context framing document must not do

- Must not argue that the system is good. That is for the reviewer to judge.
- Must not pre-answer likely criticisms.
- Must not describe features that are planned but not live.
- Must not include operational details that belong in the corpus files themselves.

## 4. Evaluation Dimensions

The reviewer evaluates the development design across these fixed dimensions. The dimensions are fixed to enable comparison across reviewers. Depth within each dimension is flexible — the reviewer goes deeper where they see more signal.

### 4.1 Fixed evaluation dimensions

**D1. Fit-to-task.** How well does the development system match the task it claims to serve? Where does it fit well? Where does it fit poorly? Which shortcomings appear local (fixable within the current design) and which appear structural (require design changes)?

**D2. Internal consistency.** Are the process documents, contracts, scripts, and templates consistent with each other? Where do they contradict, duplicate, or leave gaps?

**D3. Proportionality.** Is the system appropriately sized for its task? Where is it over-engineered (more process than the task requires)? Where is it under-specified (gaps that create risk)?

**D4. Separation of concerns.** Are the role boundaries, trust boundaries, and authority boundaries well-drawn? Are they enforced or merely stated?

**D5. Truthfulness infrastructure.** Does the system support truthful reporting of what actually happened? Can it detect or prevent false claims about execution, evidence, or routing?

**D6. Failure behavior.** How does the system behave when things go wrong? Is fail-closed behavior real and consistent, or is it stated in some places and missing in others?

**D7. Scalability pressures.** Where would the system break if task volume doubled? If a third execution agent were added? If the product surface area expanded significantly?

**D8. Maintenance burden.** How much ongoing effort does the system require to keep its documentation, contracts, and scripts consistent with actual practice? Where does this burden create drift risk?

**D9. Deterministic-check opportunities.** Where could currently judgment-dependent checks be replaced or supplemented by deterministic validation? This includes language/formatting checks, contract compliance validation, and structural consistency tests.

### 4.2 Dimension weighting

D1 (fit-to-task) carries the most weight. A system that fits its task well but has local inconsistencies is more valuable than a perfectly consistent system that doesn't fit its task.

D2-D6 are core dimensions of roughly equal weight. D7-D9 are supplementary — valuable but not required to reach a useful conclusion.

## 5. Simulation Framework

### 5.1 Purpose

Simulations are structured thought experiments that stress-test the development design against realistic scenarios. They are grounded in the documented process and artifacts, not treated as empirical proof.

### 5.2 Simulation types

**Process simulation.** Walk through a complete task lifecycle using the documented process: dispatch creation → reception check → branch execution → evidence generation → verification → merge. Identify where the process is clear, where it requires interpretation, and where it would break or stall.

*Weight: High. This is the most valuable simulation because it tests the system against its primary use case.*

**Failure simulation.** Introduce specific failure conditions and trace the system's response: missing task spec, Codex branch touching forbidden files, conflicting branches at merge time, evidence bundle with failing tests, dispatch with missing required fields. Identify which failures are caught by existing guards and which would propagate undetected.

*Weight: High. Fail-closed claims are only credible if failures are actually caught.*

**Throughput / coordination simulation.** Model a realistic high-throughput scenario: 4 concurrent Codex tasks, 2 pending merges, a hot-file conflict, and a Cecil budget approaching weekly reset. Trace how the system would coordinate, prioritize, and resolve contention. Identify bottlenecks, single points of failure, and coordination gaps.

*Weight: Medium. Useful but harder to ground precisely. The reviewer should flag coordination concerns but acknowledge that simulation of multi-agent coordination is inherently approximate.*

### 5.3 Simulation requirements

- Simulations must reference specific artifacts and documented procedures, not hypothetical procedures.
- Simulations must state assumptions explicitly.
- Simulation conclusions must be clearly labeled as simulation-derived, not observed-in-practice.
- Simulations should identify the weakest link in each scenario, not just whether the scenario succeeds or fails.

### 5.4 Reviewer discretion

The reviewer may choose which simulations to run based on where they see the most evaluative value. All three types should be attempted, but the reviewer may allocate depth based on signal. A reviewer who finds the failure simulation highly productive may go deeper there at the expense of a lighter throughput simulation.

## 6. Justification Scaling

### 6.1 The principle

Larger proposed changes require proportionally stronger justification. This is a continuous scale, not a binary gate.

### 6.2 The scale

**Level 1 — Local fix.** A specific correction to a specific artifact. Example: "MERGE_GATE.md §3 requires `git diff --stat main...HEAD` but does not specify what counts as an unexpected file."

*Required justification: identify the artifact, the specific gap, and the operational consequence.*

**Level 2 — Pattern correction.** A correction that applies across multiple artifacts. Example: "Evidence requirements are specified in EVIDENCE-CONTRACT.md, TASK_TEMPLATE.md, and MERGE_GATE.md with slight differences in required files."

*Required justification: identify all affected artifacts, the inconsistency pattern, and the proposed resolution direction.*

**Level 3 — Process change.** A change to how the development system operates. Example: "The dispatch-reception-execution-verify-merge pipeline has a verification gap: allowed-files compliance is checked at verify-task but not at reception-check in all modes."

*Required justification: identify the process gap, trace the consequence through at least one realistic scenario, and explain why a process-level change is needed rather than a local fix.*

**Level 4 — Structural redesign.** A change to the system's fundamental organization. Example: "The four-actor model creates a coordination bottleneck at Cecil because all merge authority concentrates there."

*Required justification: identify the structural pressure, provide evidence from multiple artifacts and at least one simulation, explain why the pressure cannot be addressed by lower-level changes, and propose at least one alternative architecture with tradeoff analysis.*

### 6.3 Application

The reviewer classifies each finding at the appropriate level and provides justification at that level. Findings at Level 1-2 are expected to be numerous. Findings at Level 3-4 should be fewer and more deeply argued. A review that has many Level 4 findings with Level 1 justification is poorly calibrated.

## 7. Output Contract

### 7.1 Two representations, one analysis

The review produces two synchronized output forms:

- **Human form**: narrative prose with sections, suitable for reading and productive discussion
- **Structured form**: JSON document suitable for AI ingestion, cross-review comparison, and evidence retention

These are two representations of the same underlying analysis. The structured form is the primary output — it contains all findings, evidence, and classifications. The human form is a readable rendering that may summarize or reorder for clarity but does not contain findings absent from the structured form.

### 7.2 Human form specification

```
# External Review: [Reviewer Identity / Model]

## Executive Summary
[2-5 paragraphs: overall assessment, strongest findings, most significant concerns]

## Dimension Evaluations
### D1. Fit-to-task
[Evaluation with specific artifact references]
...
### D9. Deterministic-check opportunities
[Evaluation with specific artifact references]

## Simulations Performed
### Process Simulation
[Scenario, walkthrough, findings]
### Failure Simulation
[Scenario, walkthrough, findings]
### Throughput / Coordination Simulation
[Scenario, walkthrough, findings]

## Findings by Justification Level
### Level 4 — Structural Redesign
[Findings with full justification per §6.2]
### Level 3 — Process Changes
[Findings with justification]
### Level 2 — Pattern Corrections
[Findings with justification]
### Level 1 — Local Fixes
[Findings with justification]

## Strengths Identified
[What is working well and should be preserved, with evidence]

## Deterministic Check Candidates
[Specific proposals for converting judgment-dependent checks to deterministic validation]

## Overall Assessment
[Final synthesis: is this development system well-matched to its task?]
```

### 7.3 Structured form specification

```json
{
  "review_metadata": {
    "reviewer_id": "string — model name or reviewer identity",
    "review_date": "ISO-8601",
    "corpus_version": "string — manifest hash or identifier",
    "system_version": "string — EXTERNAL_REVIEW_SYSTEM__v0"
  },
  "executive_summary": "string — 2-5 paragraph text",
  "dimension_evaluations": [
    {
      "dimension_id": "D1",
      "dimension_name": "Fit-to-task",
      "rating": "strong | adequate | mixed | weak",
      "summary": "string",
      "evidence": [
        {
          "artifact": "string — file path",
          "location": "string — section or line reference",
          "observation": "string",
          "valence": "strength | weakness | neutral"
        }
      ]
    }
  ],
  "simulations": [
    {
      "type": "process | failure | throughput_coordination",
      "scenario": "string",
      "assumptions": ["string"],
      "walkthrough": "string",
      "weakest_link": "string",
      "findings": ["string"],
      "simulation_derived": true
    }
  ],
  "findings": [
    {
      "id": "F001",
      "level": 1,
      "title": "string",
      "description": "string",
      "affected_artifacts": ["string — file paths"],
      "evidence": ["string — specific references"],
      "consequence": "string",
      "proposed_direction": "string",
      "justification_adequate": true
    }
  ],
  "strengths": [
    {
      "id": "S001",
      "title": "string",
      "description": "string",
      "evidence": ["string"],
      "preservation_recommendation": "string"
    }
  ],
  "deterministic_check_candidates": [
    {
      "id": "DC001",
      "current_check": "string — what is currently judgment-dependent",
      "proposed_check": "string — deterministic alternative",
      "affected_artifacts": ["string"],
      "implementation_complexity": "trivial | moderate | substantial"
    }
  ],
  "overall_assessment": {
    "fit_to_task": "strong | adequate | mixed | weak",
    "summary": "string",
    "top_priority_findings": ["F001", "F003"],
    "top_strengths": ["S001", "S002"]
  }
}
```

### 7.4 Synchronization rule

Every finding in the structured form must appear in the human form. Every finding in the human form must have a corresponding entry in the structured form. The human form may provide additional narrative context. The structured form may provide additional granular evidence. Neither may contain findings absent from the other.

## 8. Comparison Framework

### 8.1 How to compare multiple reviewer runs

Multiple independent reviewers evaluate the same corpus using the same dimensions and output contract. Comparison works at three levels:

**Dimension-level comparison.** For each dimension D1-D9, compare ratings across reviewers. Where reviewers agree, the finding is high-confidence. Where they disagree, the disagreement itself is informative and should be investigated.

**Finding-level comparison.** Match findings across reviewers by affected artifact and proposed direction. Findings identified by multiple reviewers independently carry higher weight. Findings identified by only one reviewer may represent genuine insight or reviewer-specific bias — both are worth examining.

**Strength-level comparison.** Strengths identified by multiple reviewers are strong candidates for preservation. Strengths identified by only one reviewer deserve scrutiny — they may be genuine or may reflect insufficient critical distance.

### 8.2 Comparison output

After multiple reviews are collected, produce a comparison summary:

```
## Cross-Review Comparison

### Consensus Findings (identified by 2+ reviewers)
[Findings with reviewer IDs and convergence notes]

### Divergent Findings (identified by 1 reviewer only)
[Findings with notes on why divergence may have occurred]

### Dimension Rating Comparison
| Dimension | Reviewer A | Reviewer B | Reviewer C | Consensus |
|---|---|---|---|---|

### Consensus Strengths
[Strengths confirmed across reviewers]

### Priority Action Items
[Ranked by cross-reviewer consensus weight]
```

### 8.3 Who produces the comparison

The comparison is produced by ChatGPT or Cecil after collecting all reviewer outputs. It is a synthesis task, not a review task. The comparator does not add new findings — it organizes and weights existing findings.

## 9. Corpus Preparation via Codex

### 9.1 Codex corpus preparation prompt

The following is a ready-to-use Codex dispatch for generating the review corpus package.

---

**BEGIN CODEX DISPATCH**

MODE: Execute
OBJECTIVE: Generate a review corpus package for external AI evaluation of the development design.

WHAT IS FIXED:
- File list and tier assignments are defined in `docs/dev/EXTERNAL_REVIEW_SYSTEM__v0.md` §2.1
- Output structure is defined below
- No file content modification — this is a packaging task only

OUTPUT CONTRACT:
Produce `docs/dev/review-corpus/` containing:

1. `MANIFEST.json` — structured manifest listing every file in the corpus with:
   - path (relative to repo root)
   - tier (1-4)
   - size_bytes
   - line_count
   - sha256 hash
   - one-line purpose description

2. `CONTEXT_FRAMING.md` — the context framing document per §3 of the review system spec. Content requirements:
   - Section A: What the project is (use docs/SCOPE.md as source, brief factual description)
   - Section B: What the development design is (not the product — the process)
   - Section C: Why the development system exists (multi-agent, capacity constraints)
   - Section D: The four actors and their roles (source: OPS_PROCESS §2)
   - Section E: What good performance looks like (source: OPS_PROCESS §3.2, AGENT_CONTRACT)
   - Section F: Current system maturity (source: ASSIGNMENTS.md history count, completion records)
   - Section G: Known tensions (throughput vs safety, autonomy vs oversight, rigor vs speed, completeness vs maintenance cost)
   - Do NOT argue the system is good. Present factual context only.

3. `CORPUS/` directory — copies of all corpus files organized by tier:
   - `CORPUS/tier1/` — core process docs
   - `CORPUS/tier2/` — operational scripts
   - `CORPUS/tier3/` — design context
   - `CORPUS/tier4/` — domain context

4. `REVIEW_PROMPT.md` — copy of the external review prompt from §10 of the review system spec

5. `STRUCTURED_OUTPUT_TEMPLATE.json` — empty template matching the structured form in §7.3

ALLOWED FILES:
- `docs/dev/review-corpus/**` (new directory)

FILES FORBIDDEN TO TOUCH:
- Everything outside `docs/dev/review-corpus/`

ACCEPTANCE CRITERIA:
- MANIFEST.json contains an entry for every corpus file with correct hash
- CONTEXT_FRAMING.md contains all 7 required sections (A-G)
- All corpus files are present in the correct tier directory
- No files outside the corpus definition are included
- REVIEW_PROMPT.md matches the spec
- STRUCTURED_OUTPUT_TEMPLATE.json is valid JSON matching §7.3 schema

STOP CONDITIONS:
- STOP if any corpus file is missing from main
- STOP if MANIFEST.json cannot be generated deterministically
- STOP if context framing requires inventing facts not in the source files

**END CODEX DISPATCH**

---

### 9.2 Representative task specs

Codex should select 5 representative READY task specs for Tier 3 inclusion. Selection criteria:
- At least one implementation task (code change)
- At least one docs-only task
- At least one investigation task
- Range of complexity (simple, medium, complex)
- Tasks that illustrate the task template format well

## 10. External Review Prompt

The following is the complete prompt given to each external AI reviewer. It is included in the corpus package as `REVIEW_PROMPT.md`.

---

**BEGIN EXTERNAL REVIEW PROMPT**

# External Review of Development Design

You are an independent reviewer evaluating a software development system's design. Your review should be thorough, honest, and grounded in the artifacts provided.

## What you are reviewing

You are reviewing the **development design** of a software project built by a multi-agent team (human and AI actors). The development design is the set of process documents, contracts, templates, scripts, and workflow infrastructure that govern how the project is built. You are not reviewing the product the system builds — you are reviewing the development system itself.

## How to begin

1. Read `CONTEXT_FRAMING.md` first. It explains what the project is, why the development system exists, who the actors are, and what good performance looks like. It does not tell you the system is good — that is for you to judge.
2. Read the `MANIFEST.json` to understand what is in the corpus.
3. Review Tier 1 (core process) and Tier 2 (operational scripts) thoroughly.
4. Review Tier 3 (design context) for background.
5. Review Tier 4 (domain context) as needed to understand what the development system is building.

## What to evaluate

Evaluate the development design across these dimensions:

- **D1. Fit-to-task.** How well does the system match the task it claims to serve? Where does it fit well? Where poorly? Are shortcomings local or structural?
- **D2. Internal consistency.** Do the documents, contracts, and scripts agree with each other?
- **D3. Proportionality.** Is the system appropriately sized? Where is it over-engineered? Under-specified?
- **D4. Separation of concerns.** Are role, trust, and authority boundaries well-drawn and enforced?
- **D5. Truthfulness infrastructure.** Does the system support truthful reporting? Can it detect false claims?
- **D6. Failure behavior.** Is fail-closed behavior real and consistent?
- **D7. Scalability pressures.** Where would the system break under growth?
- **D8. Maintenance burden.** How much effort does consistency require? Where does drift risk concentrate?
- **D9. Deterministic-check opportunities.** Where could judgment-dependent checks become deterministic?

D1 carries the most weight. D2-D6 are core. D7-D9 are supplementary.

## Simulations to perform

Perform at least one of each:

**Process simulation.** Walk through a complete task lifecycle (dispatch → reception → execution → evidence → verify → merge) using the documented process. Identify where it is clear, where it requires interpretation, and where it would break.

**Failure simulation.** Introduce a specific failure (missing spec, forbidden file touched, conflicting branches, failing tests) and trace the system's response. Which failures are caught? Which would propagate?

**Throughput simulation.** Model 4 concurrent tasks, 2 pending merges, a hot-file conflict, and a budget constraint. How does the system coordinate? Where are the bottlenecks?

Label all simulation conclusions as simulation-derived, not observed-in-practice. State assumptions explicitly.

## How to classify findings

Classify each finding at one of four levels:

- **Level 1 — Local fix.** A specific correction to a specific artifact. *Justify: identify the artifact, gap, and consequence.*
- **Level 2 — Pattern correction.** A correction across multiple artifacts. *Justify: identify all affected artifacts and the inconsistency pattern.*
- **Level 3 — Process change.** A change to how the system operates. *Justify: trace consequence through a realistic scenario.*
- **Level 4 — Structural redesign.** A change to fundamental organization. *Justify: evidence from multiple artifacts + simulation, explain why lower-level changes are insufficient, propose alternative with tradeoff analysis.*

Higher levels require proportionally stronger justification.

## What to report

Produce two synchronized outputs:

### Human-readable report

A narrative document with: executive summary, dimension evaluations (with specific artifact references), simulations performed, findings organized by justification level, strengths identified, deterministic check candidates, and overall assessment.

### Structured JSON report

A JSON document following the schema in `STRUCTURED_OUTPUT_TEMPLATE.json`. Every finding in the JSON must appear in the narrative. Every finding in the narrative must appear in the JSON.

## Important guidance

- Reference specific artifacts, sections, and lines. Ungrounded observations carry little weight.
- Surface strengths as well as weaknesses. What is working well matters.
- Distinguish local shortcomings from structural pressures.
- Do not suppress larger findings, but hold them to higher justificatory standards.
- Do not assume the system should be simpler or more complex — evaluate fit-to-task as you find it.
- Where you identify opportunities for deterministic validation (language checks, format checks, contract compliance), propose them specifically.

**END EXTERNAL REVIEW PROMPT**

---

## 11. Implementation Plan

### 11.1 Execution sequence

```
Step 1: Merge this design document to main
    |
Step 2: Codex corpus preparation (§9.1 dispatch)
    |  Produces: docs/dev/review-corpus/ with manifest, framing, corpus, prompt, template
    |
Step 3: Cecil review of corpus package
    |  Verifies: manifest accuracy, context framing truthfulness, completeness
    |
Step 4: First external review run
    |  Input: corpus package
    |  Output: human report + structured JSON
    |
Step 5: Second external review run (different model/provider)
    |  Same input, independent output
    |
Step 6: Cross-review comparison (§8)
    |  Produces: comparison summary with consensus/divergent findings
    |
Step 7: Greg + ChatGPT + Cecil discussion of results
    |  Produces: prioritized action items
```

### 11.2 Reviewer selection

For meaningful comparison, use at least two independent reviewers from different model families. Candidates:
- Claude (Opus or Sonnet) — if the review is conducted outside the project's Cecil context
- GPT-4o or o3 — different training, different priors
- Gemini 2.5 Pro — third independent perspective

The reviewer must receive only the corpus package. No additional project context, no conversation history, no hints about expected findings.

### 11.3 Timeline

- Corpus preparation: one Codex dispatch
- Each review run: one session per reviewer
- Comparison: one ChatGPT or Cecil session
- Discussion: as needed

No calendar dates. This proceeds when dispatched.

## 12. Design Decisions and Rationale

### 12.1 Why the structured form is primary

The human form is easier to read but harder to compare across reviewers. Making the structured form primary ensures every finding has a classification, evidence references, and justification level. The human form adds narrative value but cannot contain orphan findings.

### 12.2 Why fixed dimensions with flexible depth

Fixed dimensions enable apples-to-apples comparison. Flexible depth within dimensions lets each reviewer follow their signal. A reviewer who notices deep inconsistency in D2 can explore it thoroughly without being forced to spend equal time on D7.

### 12.3 Why simulations are structured thought experiments

Simulations grounded in documented process are useful precisely because they test the design's claims against realistic scenarios. But they are not empirical tests — the reviewer did not actually run the system. Labeling simulations clearly prevents false empirical authority while preserving their diagnostic value.

### 12.4 Why proportional justification rather than change-size gates

A binary gate ("redesign proposals require committee approval") would suppress legitimate structural findings. A continuous scale ("larger changes need stronger evidence") allows any finding at any level while ensuring the reviewer has done the work to justify their confidence.

### 12.5 Why the context framing document exists

Without context, an external reviewer would see disconnected process documents and evaluate them against generic software engineering priors. The context framing document explains why this system exists without arguing it is good. This enables fair evaluation — the reviewer can critique the system for not meeting its own goals rather than for not meeting goals it never claimed.

### 12.6 What I changed from the original framing

**Corpus preparation is a single Codex dispatch, not an ongoing pipeline.** The original framing implied Codex would maintain the corpus. The corpus is a point-in-time snapshot for review. Codex packages it once per review cycle.

**Simulation weight is differentiated.** The original framing asked for all three simulation forms equally. Process and failure simulations are more groundable and more valuable. Throughput simulation is useful but inherently approximate for multi-agent coordination. Weighting reflects this.

**The structured form is primary, not secondary.** The original framing said "two representations." I made the structured form primary because it is the one that enables cross-review comparison, the most valuable property of the system. The human form is a rendering, not the source of truth.

**Deterministic-check opportunities are a full dimension (D9), not a sidebar.** The original framing asked for "opportunities to derive stronger deterministic checks." This is important enough to be an evaluation dimension, not a nice-to-have appendix. Making it D9 ensures every reviewer considers it.
