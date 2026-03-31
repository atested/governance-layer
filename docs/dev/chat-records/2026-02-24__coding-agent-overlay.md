# Chat Record: Coding Agent Overlay

**Date**: 2026-02-24
**Context**: User provided DOC-READY SOURCE PACKET defining structural constraints for AI coding agents (Codex, Cecil, Qt) operating under governance. The chat focused on how to constrain AI-mediated code execution without controlling model cognition.

**Why This Chat Mattered**: Coding agents (Codex CLI, Qt worker, Cecil orchestrator) were executing code changes without explicit structural enforcement of governance principles. The system needed binding rules to prevent scope creep, ensure deterministic behavior, and maintain audit integrity across AI-generated code changes.

---

## Structured Record

### Core Concept

The **Coding Agent Overlay** is a deterministic execution control layer applied specifically to AI coding agents. **It does not change model cognition. It constrains AI-mediated code execution.**

The overlay transforms coding agents from "best effort code generators" into governed execution units whose outputs are:
- **Structured**: Task specifications with explicit Allowed Files boundaries
- **Logged**: All governed tool invocations produce audit records
- **Verifiable**: Deterministic policy evaluation before file mutation
- **Replayable**: Third parties can replay decision paths
- **Merge-disciplined**: No-ff merges, UNION conflict resolution, post-merge verification
- **Deterministically auditable**: Complete provenance from request to merge

**Canonical phrase from chat**: *"If it cannot be replayed, it is out of policy."*

### Failure Modes Prevented

The overlay exists to prevent predictable failure modes in AI-assisted development:

1. **Silent scope expansion**: Tasks mutate files outside declared boundaries
2. **Cross-file mutation without declaration**: Undeclared dependencies corrupt determinism
3. **Non-reproducible behavior**: Same inputs produce different outputs
4. **Non-deterministic merges**: Merge conflicts resolved inconsistently
5. **Loss of reasoning provenance**: Decision rationale not captured
6. **Batch burn-through without validation**: Throughput prioritized over correctness
7. **Undetected invariant violations**: Governance rules drift without detection
8. **Audit gaps in high-impact changes**: Critical mutations lack evidence trails

### Lane Responsibilities

**Codex Lane**:
- Operates only on topic branches (`codex/*`)
- Must respect Allowed Files in task headers
- Does not merge to main
- Does not modify ASSIGNMENTS.md on main
- Pushes branches to origin for Cecil review

**Cecil Lane**:
- Sole merger to main
- Resolves ASSIGNMENTS.md conflicts via UNION rule (preserve all History rows)
- Verifies invariants before merge (inventory + ops canonical)
- Performs post-merge verification
- Pushes only after verification passes

**Qt Lane**:
- Bounded worker model for QA validation
- Must not exceed prompt domain
- Terminates after bounded function
- Does not persist memory outside defined artifacts
- Writes only to `qa/test-plans/` and `qa/evidence/`

### Normative Rules (30 Total)

The chat provided 30 MUST/SHOULD/MUST NOT rules organized by category:

**File Scope & Isolation**:
1. MUST declare Allowed Files in every task
2. MUST NOT modify files outside Allowed Files
3. MUST NOT allow silent dependency injection

**Branch Discipline**:
4. MUST operate on topic branches only
5. MUST NOT merge to main from coding agent
6. MUST perform no-ff merge
7. MUST ensure clean working tree before merge

**Merge Conflicts & History**:
8. MUST resolve ASSIGNMENTS.md via UNION
9. MUST NOT drop invariant rows during conflict resolution

**Verification Gates**:
10. MUST run post-merge verification
11. MUST confirm post-merge push only after verification passes
12. MUST verify ancestor relationships before merge

**Determinism & Canonicalization**:
13. MUST normalize arguments before policy evaluation
14. MUST preserve deterministic reason ordering
15. MUST NOT introduce new invariant without documentation update

**Destructive Operations**:
16. MUST NOT overwrite without explicit cap
17. MUST declare overwrite intent explicitly
18. MUST NOT cross filesystem roots

**Logging & Audit**:
19. MUST log all governed tool actions
20. MUST NOT bypass governed_tool()
21. MUST tag high-impact actions with reason code
22. SHOULD store logs in deterministic format

**Evidence & Planning**:
23. MUST NOT skip evidence bundle when required
24. MUST separate planning from execution
25. SHOULD prefer small atomic tasks

**Batch Operations**:
26. MUST define STOP conditions in batch tasks
27. SHOULD escalate ambiguous cases to higher tier

**Worker Constraints**:
28. MUST restrict worker agents to bounded functions
29. MUST NOT mutate ACTIVE-TASK.md outside defined updates
30. SHOULD use non-interactive git

### Operational Workflows

**Single Task Flow**:
- Create topic branch from main
- Validate Allowed Files declaration
- Execute governed mutations (only within scope)
- Push to origin
- Cecil merges via no-ff with verification

**Batch/Throughput Flow**:
- Process task queue with STOP conditions
- Enforce timeout/failure limits
- Log classification (CODE vs EVIDENCE_ONLY)
- Halt on first policy denial or invariant violation

**Merge Window Protocol**:
- Prerequisites: clean main, up-to-date, verification baseline passes
- Merge with --no-ff
- Apply UNION rule for ASSIGNMENTS.md
- Run post-merge verification
- Push only after all gates pass

---

## Explicit Claims Made in Chat

- **Claim**: "The Coding Agent Overlay is a deterministic execution control layer applied specifically to AI coding agents."
- **Claim**: "It does not change model cognition. It constrains AI-mediated code execution."
- **Claim**: "Without structured enforcement, coding agents optimize for task completion speed, not traceable correctness."
- **Claim**: "The overlay prevents silent scope expansion, which corrupts determinism."
- **Claim**: "ASSIGNMENTS.md conflicts must be resolved via UNION rule: keep all History rows from main and append incoming rows."
- **Claim**: "If it cannot be replayed, it is out of policy." (Canonical phrase)
- **Claim**: "Cecil is the sole merger to main. Merge authority centralization ensures deterministic conflict resolution."
- **Claim**: "Codex operates as a governed execution unit. All outputs must pass through Cecil's merge gate."
- **Claim**: "Qt operates as a mechanical validation unit. Bounded execution prevents scope drift."
- **Claim**: "Merge authority centralization prevents coordination failures."
- **Claim**: "The system is continuous learning, 'always reducing judgment,' rather than reaching a done state."
- **Claim**: "Trust laundering prevention is a core invariant: analogies and summaries cannot become authoritative without canonical backing."
- **Claim**: "Evidence gating is required for high-impact changes: must cite prior state, justification, trust basis."
- **Claim**: "Governed tool boundary: all file mutations must go through governed_tool() wrappers. Direct file access prohibited."
- **Claim**: "The overlay transforms development from 'AI writes code' to 'AI proposes structured mutations that pass invariant discipline before integration.'"

---

## Key Quotes from Chat

> "If it cannot be replayed, it is out of policy."

> "It does not change model cognition. It constrains AI-mediated code execution."

> "Without structured enforcement, coding agents optimize for task completion speed, not traceable correctness."

> "Keep all History rows from main and append incoming rows; never drop." (UNION rule)

> "Cecil is the governance enforcer."

> "AI proposes structured mutations that pass invariant discipline before integration."
