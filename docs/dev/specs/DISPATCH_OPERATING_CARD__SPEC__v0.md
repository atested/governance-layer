# Dispatch Operating Card Specification

Version: v0 (planning draft)
Status: Phase 1 specification — not yet operational
Deployment: Canonical copy in repo; working copy as GPT project file

## 1. Purpose

1.1. The dispatch operating card defines mandatory ChatGPT behavior for framing, packaging, and dispatching work to Codex.

1.2. It ensures that every Codex-facing dispatch meets the readiness threshold: Codex can stop interpreting and start organizing.

1.3. It does not replace OPS_PROCESS v1 or DISPATCH_LIBRARY v10. It extends Section 9.1 of OPS_PROCESS v1 with a richer dispatch structure and adds operating defaults for batch shaping, mode selection, and shared-state maintenance.

## 2. Mandatory Dispatch Standard

Every Codex-facing dispatch MUST include the following elements. For simple single-lane tasks, elements 3 and 4 MAY be brief, but MUST still be present.

### 2.1. Mode Declaration

Every dispatch MUST declare one of:
- **Execute**: Build, implement, test. Output is code changes, test results, evidence artifacts.
- **Investigate**: Explore, analyze, compare, assess, prepare. Output is a report or analysis artifact.

### 2.2. Shared Frame (MUST appear first)

Every dispatch MUST include:

1. **Objective**: What the work must accomplish.
2. **Why now**: Why this work matters at this point in the project.
3. **What is fixed**: What MUST NOT change. Includes invariants, constraints, and non-goals.
4. **Preservation constraints**: Specific files, behaviors, or contracts that MUST be preserved.

### 2.3. Lane Structure (MUST appear second, if applicable)

If the dispatch contains parallel work:

1. **Lanes**: Each lane MUST have a distinct identifier.
2. **Lane question**: Each lane MUST state the specific question it answers.
3. **Lane boundary**: Each lane MUST state what is in scope and out of scope for that lane.
4. **Lane return contract**: Each lane MUST state what output it produces and in what format.

If the dispatch is a single-lane task, this section MAY be a single line: "Single lane."

### 2.4. Synthesis Contract (MUST appear third, if multi-lane)

If the dispatch contains parallel lanes:

1. **Synthesis action**: One of: compare, draft-single, reconcile, escalate-contradictions.
2. **Final artifact**: What the synthesized output must be.
3. **Synthesis location**: Where the final artifact lands.

If the dispatch is a single-lane task, this section MAY be omitted.

### 2.5. Output Contract

Every dispatch MUST include:

1. **Expected output type**: Code changes, report file, analysis document, evidence bundle, etc.
2. **Landing location**: Where output files MUST be placed.
3. **Reporting format**: Reference to the applicable report format. At Phase 1, this is the completion-line standard: every report MUST end with `COMPLETE: [report type] for [subject]. [Outcome sentence].`
4. **Acceptance boundary**: What "done" looks like. Specific, testable criteria.

### 2.6. STOP Conditions

Every dispatch MUST include explicit STOP conditions. At minimum:

1. Inherited STOP conditions from OPS_PROCESS v1 Section 6 (fail-closed on missing specs, allowlists, hot-file violations).
2. Any task-specific STOP conditions.

The STOP section MUST appear at the end of the dispatch, clearly separated.

## 3. Inherited Requirements

The dispatch operating card does not replace existing dispatch requirements. The following remain mandatory:

### 3.1. From OPS_PROCESS v1 Section 9.1

1. Base SHA expectations
2. Hot file list and "do not touch" rules
3. Explicit list of tasks to execute
4. Per-task reporting requirements (branch name, diff stat, evidence tail, deterministic hashes, STOP reasons)

### 3.2. From DISPATCH_LIBRARY v10

1. Mandatory preflight: `task-id-guard.sh` collision check for restock/publish batches
2. Validation-scope expansion for sensitive surfaces (TOUCHED_SENSITIVE_SURFACES, REQUIRED_ADJACENT_GATES, ADJACENT_GATE_STATUS, MISSING_GATE_COVERAGE)
3. Fail-closed on guard failure or missing gate coverage

## 4. Greg-Review Trigger Handling

### 4.1. Mandatory Greg-Review Triggers

ChatGPT MUST surface these to Greg during discussion and MUST NOT dispatch until Greg confirms:

1. Task changes canonical operating documents (OPS_PROCESS, OPS_CANONICAL, DISPATCH_LIBRARY, MERGE_GATE, AGENT_CONTRACT, RUNBOOK, BFPS).
2. Task implies role-boundary or merge-authority change.
3. Task introduces or expands sisters/QT integration into a new lane type not previously approved.
4. Task depends on current conditions that ChatGPT cannot verify from CURRENT_CONDITIONS.md.

### 4.2. Notable Conditions (surface but do not block)

ChatGPT SHOULD note these to Greg but MAY proceed if the dispatch is otherwise well-formed:

1. Unusually large batch (more files or more lanes than typical).
2. First use of a new routing pattern within an already-approved mode.
3. Task touches files on the hot-file list.
4. Task requires accepting non-trivial conflict risk with in-flight branches.
5. Task introduces a new shared-store field or reporting element.

### 4.3. Not Triggers

The following MUST NOT be treated as Greg-review triggers:

1. Routine execution dispatches within established patterns.
2. Investigation dispatches within established patterns.
3. Shared-store updates within defined schema.

## 5. Batch Coherence Check

### 5.1. Before Every Dispatch

ChatGPT MUST read CURRENT_CONDITIONS.md and check:

1. **File-path overlap**: Do any key files in the proposed dispatch overlap with key files in any in-flight branch listed in the In-Flight table?
2. **Blocker check**: Are there active blockers that affect the proposed work?
3. **Main SHA currency**: Is the Main SHA current, or has a merge landed since the last update?

### 5.2. If Overlap Is Detected

ChatGPT MUST do one of:
1. Sequence the batches (hold the new dispatch until the overlapping branch merges).
2. Split the overlapping work into a non-overlapping dispatch.
3. Surface the conflict risk to Greg as a notable condition (Section 4.2.4).

ChatGPT MUST NOT dispatch overlapping work without acknowledgment.

## 6. Shared-Store Responsibilities

### 6.1. ChatGPT State Authority

ChatGPT is the primary logical state authority for CURRENT_CONDITIONS.md. ChatGPT determines what updates are needed after each of:
1. Dispatching work to Codex.
2. Receiving a Codex completion result.
3. Receiving a Cecil merge report.
4. Learning of a new blocker or blocker resolution.

ChatGPT MUST include the specific CURRENT_CONDITIONS update instructions in the relevant dispatch or follow-up instruction to a repo-capable agent (Codex or Cecil). ChatGPT does not write to the file directly.

### 6.2. Mechanical Writers

Codex and Cecil perform actual writes to CURRENT_CONDITIONS.md. Codex applies update instructions included in ChatGPT dispatches. Cecil writes merge-authoritative sections (Last Merge, Merge Quality, Main SHA) after merge completion without requiring ChatGPT instruction.

### 6.3. State-Change Reality Rule

A CURRENT_CONDITIONS change is not real until a repo-capable agent has written it. ChatGPT MUST NOT treat a state change as effective until the mechanical writer confirms the write.

### 6.4. ChatGPT MUST Read CURRENT_CONDITIONS.md

ChatGPT MUST read the shared store before preparing any dispatch (Section 5.1). ChatGPT reads via Codex read operation or Greg-provided paste.

## 7. Cecil Engagement Rule

### 7.1. When to Engage Cecil

Cecil is engaged ONLY for:
1. Final merge execution to main.
2. Final merge acceptance or rejection judgment.
3. Semantic cross-branch conflict resolution.
4. Merge-order decisions where reordering changes semantic outcome.
5. Architectural arbitration where merge implies design-level choice.
6. Policy-boundary decisions.
7. Exploratory design evaluation and architectural review.

### 7.2. When NOT to Engage Cecil

Cecil MUST NOT be engaged for mechanical merge-adjacent work that Codex can perform:
1. Completion packet validation.
2. Remote publication verification.
3. Diffstat generation.
4. File-overlap detection at structural file-path level.
5. Basic conflict detection at structural level.
6. Merge candidate clustering.
7. Merge candidate inventory.

These become relevant in Phase 3. At Phase 1, this section establishes the principle only.

## 8. What MUST NOT Live in the Operating Card

1. Detailed repo knowledge or file contents.
2. Task history or branch state (those live in CURRENT_CONDITIONS.md).
3. BFPS content or session handoff information.
4. Full report format specifications (those live in the report format reference, Phase 2).
5. Merge dispatch templates (those live in DISPATCH_LIBRARY via CANON pointer).
6. Task specifications or evidence contracts.

## 9. Deployment

### 9.1. Canonical Copy

The canonical copy of the dispatch operating card lives in this specification file in the repo. Any changes MUST be made here first.

### 9.2. GPT Project File Copy

A working copy is maintained as a GPT project file for ChatGPT session access. ChatGPT SHOULD verify the project file matches the canonical repo copy at session start. If they diverge, the repo copy is authoritative.

### 9.3. Update Cadence

When the canonical spec changes, ChatGPT MUST update the GPT project file copy at the next session start.
