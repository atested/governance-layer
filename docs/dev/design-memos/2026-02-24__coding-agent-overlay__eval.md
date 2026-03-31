# Evaluation Memo: Coding Agent Overlay

**Date**: 2026-02-24
**Status**: [IMPLEMENTED]
**Evaluator**: Cecil (governance operator)

---

## What It Is

The **Coding Agent Overlay** is a deterministic execution control layer that constrains how AI coding agents (Codex CLI, Cecil, Qt, routed workers) plan, generate, modify, verify, merge, and audit code. It applies structural behavioral constraints to AI-mediated code execution without attempting to control model cognition.

The overlay defines:
- **Lane responsibilities** (Codex: topic branches only, Cecil: sole merger, Qt: bounded worker)
- **30 normative rules** (MUST/SHOULD/MUST NOT constraints organized by category)
- **Operational workflows** (single task, batch/throughput, merge window protocols)
- **Failure modes** (10 predictable failures with symptom → cause → recovery → preventive rule)
- **Canonical phrases** ("If it cannot be replayed, it is out of policy")

---

## Problem It Solves (Failure Modes)

The overlay prevents 8 predictable failure modes in AI-assisted development:

1. **Silent scope expansion**: Tasks mutate files outside declared boundaries → breaks audit isolation
2. **Cross-file mutation without declaration**: Undeclared dependencies → corrupts determinism
3. **Non-reproducible behavior**: Same inputs produce different outputs → breaks replay verification
4. **Non-deterministic merges**: Merge conflicts resolved inconsistently → corrupts provenance
5. **Loss of reasoning provenance**: Decision rationale not captured → breaks traceability
6. **Batch burn-through without validation**: Throughput prioritized over correctness → undetected corruption
7. **Undetected invariant violations**: Governance rules drift without detection → structural decay
8. **Audit gaps in high-impact changes**: Critical mutations lack evidence trails → trust laundering

**Root cause addressed**: Without structural enforcement, coding agents optimize for task completion speed, not traceable correctness.

---

## Fit with Governance Layer NOW

### Reuse (Existing Primitives)

The overlay **builds on existing governance-layer primitives**:
- **policy-eval.py**: Already enforces Allowed Files via RC-FS-PATH-DISALLOWED
- **Governed tools**: FS_WRITE, FS_MOVE, FS_DELETE already use governed_tool() wrappers
- **Decision chains**: decision-chain.jsonl already provides append-only audit log
- **Reason codes**: RC-* taxonomy already provides structured denial reasons
- **Capability registry**: Already defines normalized argument contracts
- **Replay verification**: verify-chain.py already validates record integrity

The overlay **does not add new enforcement primitives**. It structures how agents use existing tools.

### Conflicts (None Identified)

No conflicts with existing governance-layer guarantees:
- Overlay strengthens determinism (does not weaken it)
- Overlay adds workflow constraints (does not relax existing policy rules)
- Overlay makes audit explicit (does not bypass decision records)

### Invariants Required

The overlay **requires** the following invariants to be enforced:

**Already Implemented**:
- Fail-closed posture (policy denials stop execution)
- Deterministic policy evaluation (same inputs → same decision)
- Replayable decision paths (verify-chain.py validates)
- Governed tool boundary (all mutations go through policy-eval.py)

**Newly Formalized by Overlay**:
- **Merge authority centralization**: Only Cecil merges to main (operational process, not code enforcement)
- **UNION conflict resolution**: ASSIGNMENTS.md conflicts preserve all History rows (manual protocol, verified via grep count)
- **No-ff merge requirement**: All merges use `--no-ff` (git workflow, not policy-eval.py)
- **Post-merge verification gates**: inventory + ops canonical checks must pass before push (script-based gates)

**Implementation surface**: The overlay invariants are enforced through **operational discipline** (RUNBOOK.md procedures) and **helper scripts** (codex-unattended.sh, merge protocol), not through policy-eval.py rule changes.

---

## Implementation Surface (Areas Touched)

If this overlay were to be added incrementally, the following areas would be touched:

### Documentation (Primary Surface)

- **RUNBOOK.md**: Add operational workflows (single task, batch, merge window)
- **OPS_CANONICAL.md**: Define lanes (Codex/Cecil/Qt), invariants, merge protocol
- **AGENT_CONTRACT.md**: Add 30 normative rules organized by category
- **GOVERNANCE_OVERVIEW.md**: Add overlay section explaining scope and guarantees

### Scripts (Supporting Surface)

- **codex-unattended.sh**: Already implements Allowed Files enforcement + evidence validation
- **cecil-runloop.sh**: Already implements merge protocol with verification gates
- **queue-claim.sh**: Already implements task claiming (Cecil lane only)
- **inventory-snapshot.sh**: Already used for post-merge verification

### Policy Engine (No Changes Required)

- **policy-eval.py**: No changes needed (Allowed Files enforcement already exists via RC-FS-PATH-DISALLOWED)
- **capability-registry.json**: No changes needed (normalized args already defined)
- **MCP server**: No changes needed (governed tools already wrap mutations)

### Verification Tools (No Changes Required)

- **verify-ops-canonical.py**: Already validates script allowlist and invariant checks
- **verify-chain.py**: Already validates decision chain integrity

---

## Risks and Open Questions

### Risks

1. **Operational discipline reliance**: The overlay depends on Cecil and Codex following RUNBOOK.md procedures. If humans bypass the protocol (direct git push, manual file edits), the overlay cannot enforce constraints.

   **Mitigation**: Document canonical workflows clearly. Use helper scripts to reduce manual steps. Enforce post-merge verification as a gate.

2. **UNION rule manual enforcement**: ASSIGNMENTS.md conflict resolution requires manual UNION merge with grep count validation. Automated tooling is prohibited to ensure conscious decisions, but this creates human error risk.

   **Mitigation**: Explicit STOP conditions in merge protocol. Document grep verification pattern. Fail merge if count mismatch detected.

3. **Scope creep in task specs**: If task Allowed Files are defined too broadly, the overlay cannot prevent mutations outside true task scope (e.g., `**/*.md` allows any markdown file).

   **Mitigation**: Code review of task specs. Prefer explicit file lists over broad globs. Codex-unattended.sh validates Allowed Files exist.

4. **Qt bounded execution enforcement**: Qt lane relies on prompt design to enforce bounded execution. If prompts allow scope expansion, Qt can exceed bounded function.

   **Mitigation**: Standardize Qt prompts. Add output validation checks. Restrict Qt to write-only paths (`qa/test-plans/`, `qa/evidence/`).

### Open Questions

1. **How should the overlay handle lane violations?** (e.g., Codex attempts to merge to main)
   - Current: Operational process prevents this (Codex has no merge authority)
   - Future: Could add pre-push hook to reject pushes to main from Codex branches?

2. **What constitutes adequate evidence for high-impact changes?**
   - Current: Evidence bundles include TESTS.txt with `[exit=N]` markers
   - Future: Define evidence taxonomy with required fields (test plan, fixtures, exit codes, coverage)?

3. **How should batch STOP conditions be enforced?**
   - Current: Timeout enforcement in throughput loop (OPS_PHASE4A)
   - Future: Add policy-based STOP signals (e.g., RC-BATCH-LIMIT-EXCEEDED)?

4. **How should the overlay evolve as new agent types are added?**
   - Current: Three lanes defined (Codex, Cecil, Qt)
   - Future: Add lane definition template? Require explicit lane registration in OPS_CANONICAL.md?

5. **Should Allowed Files enforcement be stricter?**
   - Current: RC-FS-PATH-DISALLOWED denies mutations outside Allowed Files
   - Future: Add RC-FS-GLOB-TOO-BROAD to warn on overly permissive globs (e.g., `**/*`)?

---

## Go / No-Go Criteria

### Go Criteria (Conditions for Adoption)

This overlay should be adopted if:

1. **AI coding agents are making unstructured changes** (scope creep, undeclared mutations)
2. **Merge conflicts are being resolved inconsistently** (History rows dropped, non-deterministic resolution)
3. **Audit trails have gaps** (file mutations not logged, decision rationale missing)
4. **Batch operations complete without verification** (throughput prioritized over correctness)
5. **Governance rules drift without detection** (docs diverge from implementation)

**Threshold**: If 3+ of these conditions are observed, the overlay provides clear value.

### No-Go Criteria (Conditions for Rejection)

This overlay should NOT be adopted if:

1. **All coding is manual** (no AI agents, no automation) → overlay adds overhead without benefit
2. **No merge conflicts occur** (single contributor, no concurrent branches) → UNION rule unnecessary
3. **Audit requirements are minimal** (low-stakes project, no compliance needs) → logging overhead unjustified
4. **Determinism is not a goal** (exploratory work, prototyping) → reproducibility constraints too restrictive

**Current Assessment**: The governance-layer project meets ALL go criteria. The overlay is **[IMPLEMENTED]** operationally via RUNBOOK.md procedures and helper scripts.

---

## Status and Next Steps

**Status**: [IMPLEMENTED]

The overlay is currently operational:
- Lane responsibilities documented in OPS_CANONICAL.md
- Operational workflows documented in RUNBOOK.md
- Normative rules documented in AGENT_CONTRACT.md
- Helper scripts enforce Allowed Files, evidence validation, merge protocol

**Remaining Work** (if incremental formalization desired):
- Add explicit lane registration mechanism (currently implicit via script allowlist)
- Strengthen evidence taxonomy (define required fields beyond TESTS.txt)
- Add pre-push hooks to enforce lane constraints (currently operational discipline only)
- Expand STOP condition taxonomy for batch operations (currently timeout-based)

**No blockers identified** for continued operation under current implementation.
