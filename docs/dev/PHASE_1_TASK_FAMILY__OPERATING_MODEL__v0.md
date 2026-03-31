# Phase 1 Task Family: Operating Model Implementation

Version: v0
Status: Task planning — not yet authorized for execution
Scope: Phase 1 only — dispatch operating card, shared current-conditions store, Codex reception checklist

## 1. Purpose

Convert the Phase 1 planning package into bounded implementation tasks that can be given to Codex and/or Cecil without ambiguity.

## 2. Scope

Phase 1 implementation only. No Phase 2–5 tasks. No edits to existing canonical files (OPS_PROCESS v1, OPS_CANONICAL, DISPATCH_LIBRARY v10, MERGE_GATE, AGENT_CONTRACT, RUNBOOK, BFPS v12).

## 3. Inputs

1. `docs/dev/PHASE_1_IMPLEMENTATION_PLAN__OPERATING_MODEL__v0.md`
2. `docs/dev/specs/DISPATCH_OPERATING_CARD__SPEC__v0.md`
3. `docs/dev/specs/CURRENT_CONDITIONS__SPEC__v0.md`
4. `docs/dev/specs/CODEX_RECEPTION_CHECKLIST__SPEC__v0.md`
5. `docs/dev/notes/PHASE_1_IMPLEMENTATION_SUMMARY__v0.md`
6. Accepted CURRENT_CONDITIONS ownership correction (logical authority vs mechanical writer)
7. Accepted Round 2 delta refinements

## 4. Settled Decisions

4.1. Shared store location: `docs/dev/CURRENT_CONDITIONS.md`
4.2. Dispatch standard: mandatory with lightweight minimum for simple tasks.
4.3. ChatGPT is logical state authority for CURRENT_CONDITIONS. Codex and Cecil are mechanical repo writers.
4.4. A CURRENT_CONDITIONS change is not real until a repo-capable agent has written it.
4.5. Section ownership is explicit per the corrected ownership model.
4.6. CURRENT_CONDITIONS.md is NOT added to the hot-file list at Phase 1.
4.7. GPT project file copy is updated at next session start after any spec change.
4.8. Minimal always-on reset line in every operational report.
4.9. Completion-line standard: `COMPLETE: [report type] for [subject]. [Outcome sentence].`

## 5. Task-Family Design Principles

5.1. Prefer the smallest number of coherent tasks that preserve clean ownership, low merge friction, and clear acceptance boundaries.

5.2. Do not create a separate task for each file when files are closely related, share no overlap risk with other work, and benefit from being authored together for internal consistency.

5.3. Repo-side implementation tasks are distinct from operational adoption milestones. Repo tasks create or modify artifacts in the repo. Operational milestones involve agents adopting new behaviors.

## 6. Task Count Decision

**Recommendation: TWO tasks.**

### 6.1. Why Two, Not One

The Phase 1 implementation has two distinct concerns with different executor fit:

- **Concern A: Spec correction + live store creation.** This is repo work: patch the CURRENT_CONDITIONS spec with the ownership correction, update the dispatch-card spec's shared-store section to match, and create the live CURRENT_CONDITIONS.md file. This is Codex-suitable work with clear file scope and testable acceptance criteria.

- **Concern B: Operational adoption verification.** This confirms the new standard works in practice: ChatGPT uses the dispatch card, Codex applies the reception checklist, CURRENT_CONDITIONS.md is maintained through real operations. This is a cross-agent operational pilot, not a repo-modification task.

Combining them into one task would mix repo implementation with operational process verification, making acceptance criteria ambiguous. Separating them preserves clean ownership.

### 6.2. Why Two, Not Three

There is no benefit to separating the spec correction from the live-store creation. They touch non-overlapping files within the same planning family, they share no hot-file sensitivity, and the live store must conform to the corrected spec, so authoring them together ensures consistency. Separating them would add a merge boundary with zero benefit.

## 7. Ordered Implementation Tasks

---

### Task P1-IMPL-01: Apply Ownership Correction and Create Live Store

**Task ID:** P1-IMPL-01
**Objective:** Apply the accepted CURRENT_CONDITIONS ownership correction to the spec, update the dispatch-card spec's shared-store section for consistency, and create the initial live `docs/dev/CURRENT_CONDITIONS.md` file with correct schema and ownership model.

**Why this task is separated:** This is the repo-side implementation work. It creates and corrects artifacts that must exist before the operational pilot can begin.

**Exact files in scope:**

| File | Action |
|---|---|
| `docs/dev/specs/CURRENT_CONDITIONS__SPEC__v0.md` | MODIFY — replace Sections 3, 4, 5 with corrected ownership model |
| `docs/dev/specs/DISPATCH_OPERATING_CARD__SPEC__v0.md` | MODIFY — update Section 6 (Shared-Store Responsibilities) to reflect that ChatGPT is logical authority but Codex/Cecil are mechanical writers |
| `docs/dev/CURRENT_CONDITIONS.md` | CREATE — initial live store with correct schema, populated with current conditions at creation time |

**Exact files out of scope:**

All files not listed above. Specifically:
- All existing canonical files (OPS_PROCESS v1, OPS_CANONICAL, DISPATCH_LIBRARY v10, MERGE_GATE, AGENT_CONTRACT, RUNBOOK, BFPS v12)
- `docs/dev/specs/CODEX_RECEPTION_CHECKLIST__SPEC__v0.md` (no changes needed)
- `docs/dev/PHASE_1_IMPLEMENTATION_PLAN__OPERATING_MODEL__v0.md` (planning artifact, not modified by implementation)
- `docs/dev/notes/PHASE_1_IMPLEMENTATION_SUMMARY__v0.md` (summary, not modified)
- All hot files

**Acceptance criteria:**

1. `CURRENT_CONDITIONS__SPEC__v0.md` Section 3 defines logical state authority vs mechanical repo writer distinction.
2. `CURRENT_CONDITIONS__SPEC__v0.md` Section 3A defines section-ownership table with explicit per-section logical authority and mechanical writer.
3. `CURRENT_CONDITIONS__SPEC__v0.md` Section 3A.1 defines section-protection rule.
4. `CURRENT_CONDITIONS__SPEC__v0.md` includes state-change reality rule: a change is real only after a repo-capable agent has written it.
5. `CURRENT_CONDITIONS__SPEC__v0.md` Section 4 includes corrected read rules reflecting that ChatGPT reads via Codex read or Greg-provided paste.
6. `CURRENT_CONDITIONS__SPEC__v0.md` Section 5 includes corrected update rules specifying that ChatGPT includes update instructions in dispatches, and Codex/Cecil apply them.
7. `DISPATCH_OPERATING_CARD__SPEC__v0.md` Section 6 is updated to state that ChatGPT specifies desired CURRENT_CONDITIONS updates in dispatches, and that Codex applies them as the mechanical writer.
8. `docs/dev/CURRENT_CONDITIONS.md` exists with the exact schema from the spec Section 2.
9. `docs/dev/CURRENT_CONDITIONS.md` is populated with current conditions at creation time (current origin/main SHA, empty In-Flight table, placeholder Last Merge and Last Dispatch reflecting no prior Phase 1 activity).
10. No files outside the in-scope list are modified.
11. All three files are internally consistent with the ownership correction.

**Preferred executor:** Codex

**Rationale:** Bounded spec modification and file creation with clear acceptance criteria. No architectural judgment required. Codex can apply the ownership correction language from the accepted delta and create the live store from the spec schema.

**Collaborative:** No. Single-executor task.

**Parallel-safe:** Yes. No file overlap with any other in-flight work. No hot files.

**Dependencies:** None. This is the first task in the family.

**Merge sensitivity:** LOW. Touches only Phase 1 planning artifacts (specs/) and creates one new file (CURRENT_CONDITIONS.md). No hot files. No overlap with existing canonical files. Can be merged independently.

---

### Task P1-ADOPT-01: Phase 1 Operational Adoption Pilot

**Task ID:** P1-ADOPT-01
**Objective:** Verify that the Phase 1 operating model works in practice by running 3–5 real Codex dispatches using the dispatch standard, applying the Codex reception checklist, and maintaining CURRENT_CONDITIONS.md through real operations.

**Why this task is separated:** This is operational verification, not repo implementation. It tests the new standard in real use rather than creating artifacts.

**Exact files in scope:**

| File | Action |
|---|---|
| `docs/dev/CURRENT_CONDITIONS.md` | UPDATE — maintained through real operations per the corrected ownership model |
| GPT project file (external) | CREATE — copy of dispatch operating card for ChatGPT session access |
| Codex project-level instruction (external) | CREATE — reception checklist in concise operational form |

**Exact files out of scope:**

- All spec files (no spec changes during pilot)
- All existing canonical files
- All hot files

**Acceptance criteria:**

1. ChatGPT dispatch operating card exists as a GPT project file.
2. Codex reception checklist is active as a project-level instruction.
3. At least 3 real Codex dispatches have been framed using the mandatory dispatch standard (mode, frame, output contract, STOP conditions).
4. Codex reception checklist has been applied to at least 3 incoming dispatches (missing-element validation performed).
5. CURRENT_CONDITIONS.md has been updated at least 3 times during real operations by repo-capable agents (Codex and/or Cecil), following the corrected ownership model.
6. No state-change-reality-rule violations observed (ChatGPT did not assume a CURRENT_CONDITIONS change was real before a repo writer applied it).
7. No existing canonical files have been modified.
8. Greg has reviewed pilot results.

**Preferred executor:** Cross-agent (ChatGPT + Codex + Cecil during normal operations)

**Rationale:** This is not a single-executor repo task. It is an operational verification milestone that occurs naturally during real work. ChatGPT adopts the dispatch card. Codex applies the reception checklist. Codex and Cecil write to CURRENT_CONDITIONS.md per the ownership model. Greg observes results.

**Collaborative:** Yes. Requires ChatGPT, Codex, Cecil, and Greg.

**Parallel-safe:** Yes. Occurs during normal operations, not as a blocking gate.

**Dependencies:** P1-IMPL-01 MUST be complete and merged before this pilot begins.

**Merge sensitivity:** NONE for the pilot itself. CURRENT_CONDITIONS.md updates are normal operations, not task-branch changes.

---

## 8. Recommended Execution Order

```
P1-IMPL-01: Apply ownership correction + create live store
    ↓ (merge to main)
P1-ADOPT-01: Operational adoption pilot (3-5 dispatches)
    ↓ (Greg evaluation)
Phase 1 acceptance criteria assessment
    ↓ (Greg decision)
Phase 2 planning begins (if Phase 1 accepted)
```

P1-IMPL-01 MUST complete and merge before P1-ADOPT-01 begins. The pilot requires the corrected specs and live store to exist on main.

## 9. Recommended Merge Strategy

9.1. P1-IMPL-01 produces a single branch (e.g., `codex/P1_IMPL_01__operating_model_store__v1`).
9.2. The branch touches only spec files and creates one new file. No hot-file contact. No overlap with existing in-flight work.
9.3. Merge via standard Cecil merge to main. Merge window size: M1 (minimal unblock).
9.4. P1-ADOPT-01 does not produce a branch. It occurs during normal operations.

## 10. Immediate Next Task Recommendation

**Execute P1-IMPL-01.**

This is the smallest bounded step that moves Phase 1 from planning to implementation. It has:
- Clear file scope (3 files)
- Clear acceptance criteria (11 points)
- No hot-file sensitivity
- No dependencies on other in-flight work
- Low merge friction (new file + spec patches within planning family)

After P1-IMPL-01 merges, the operational pilot (P1-ADOPT-01) can begin immediately as part of the next real work cycle.

## 11. Open Decisions

11.1. **CURRENT_CONDITIONS.md initial population.** The live store MUST be populated with current conditions at creation time. The task executor MUST determine the current origin/main SHA and set Last Merge / Last Dispatch to initial-state placeholders. No Greg decision needed — this is mechanical.

11.2. **Codex reception checklist deployment form.** The spec defines this as a "project-level instruction." The exact mechanism for deploying a project-level instruction to Codex depends on Greg's Codex configuration. Greg MUST confirm how to deploy the reception checklist before P1-ADOPT-01 begins. Options: paste into Codex project instructions, include as a dispatch preamble, or store as a repo file that dispatches reference.

11.3. **Dispatch operating card GPT project file creation.** Greg MUST confirm when to create the GPT project file copy. Recommendation: immediately after P1-IMPL-01 merges.
