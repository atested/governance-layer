# Evaluation Memo: Model Delta Engine / State Transfer under Governance

**Date**: 2026-02-24
**Status**: [SPECULATIVE]
**Evaluator**: Cecil (governance operator)

---

## What It Is

The **Model Delta Engine** is a conceptual reframing of the governance-layer (and related systems) as a **state transfer engine** that moves from one structured model to another under strict audit and verification constraints.

The pattern defines:
- **Source state (S)**: Current model (e.g., tool request, current file state, policy V1)
- **Target state (T)**: Desired model (e.g., authorized mutation, updated file, policy V2)
- **Delta (G, D)**: Gaps and dependencies between S and T
- **Transform plan (P)**: Sequence of steps with explicit preconditions and postconditions
- **Verification (V)**: Checks that must pass before each step is accepted
- **Audit trace**: Links from every step back to canonical constraints and evidence

**Canonical phrase**: *"Advance when reality agrees"* - verification gates progression through state transitions.

**Key insight**: Governance-layer is not just "policy enforcement" but an instance of this broader state transfer pattern. Other applications (decision compression, cross-team translation, schema migration) could use the same structural primitives.

---

## Problem It Solves (Failure Modes)

The Model Delta Engine framing addresses conceptual and operational failure modes:

### Conceptual Failure Modes

1. **Narrow self-understanding**: Viewing governance-layer only as "policy denial engine" misses broader applicability (state transitions, migration, learning)
2. **Missed reuse opportunities**: Different problems (domain translation, schema migration, learning) solved with bespoke approaches instead of shared primitives
3. **Lack of failure taxonomy**: Errors attributed to "AI hallucination" or "bad luck" instead of traceable causes (mapping error, missing constraint, insufficient verification)
4. **Trust laundering**: Explanations and analogies promoted to canonical claims without evidence backing
5. **Judgment zone creep**: Discretionary decisions accumulate without systematic reduction via structural differentiation

### Operational Failure Modes

6. **Non-traceable failures**: When errors occur, insufficient provenance to identify "what preceded it" (ambiguity vs missing constraint vs unrecognized judgment)
7. **Non-deterministic transitions**: Same inputs produce different outputs due to unnormalized state or unlogged decisions
8. **Audit gaps**: State transitions occur without decision records, breaking replay verification
9. **Narrative drift**: Over time, assumptions and simplifications diverge from canonical constraints without detection

**Root cause addressed**: Without a unified abstraction, each problem is solved in isolation, accumulating technical debt and missed learning opportunities.

---

## Fit with Governance Layer NOW

### Reuse (Existing Primitives That Already Implement This Pattern)

The governance-layer **already implements** the Model Delta Engine pattern for tool execution:

| Pattern Component | Governance-Layer Implementation |
|---|---|
| **Source (S)** | Tool request + intent + current filesystem/policy state |
| **Target (T)** | Executed tool action + new filesystem/policy state |
| **Bridge (M)** | Policy rules (capability registry, path allowlists, intent validation) |
| **Delta (G, D)** | Policy evaluation result (ALLOW/DENY + reason codes) |
| **Transform plan (P)** | Governed tool execution (single step, sequenced in chains) |
| **Verification (V)** | Policy checks (RC-* denial reasons enforce constraints) |
| **Audit trace** | Decision records with cryptographic hashes (decision-chain.jsonl) |

**Evidence**: policy-eval.py takes tool request (S), evaluates against policy (M), computes decision (G, D), produces audit record with normalized args (P), and enforces verification before execution (V).

### Conflicts (Conceptual, Not Technical)

No technical conflicts identified. The framing is **additive** - it reinterprets existing behavior through a more general lens.

**Conceptual tension**: The governance-layer documentation currently emphasizes "policy enforcement" and "fail-closed posture." The Model Delta Engine framing emphasizes "state transitions" and "verification-gated progression." These are compatible but highlight different aspects.

**Resolution**: Both framings are valid. Policy enforcement is the governance-layer's **current use case**. State transfer is the **underlying pattern** that could generalize to other use cases.

### Invariants Required (Already Present)

The Model Delta Engine framing **requires** invariants that governance-layer already enforces:

- **Deterministic evaluation**: Same S + M → same decision (already enforced via normalized args)
- **Replay verification**: Any transition can be independently replayed (already enforced via decision-chain.jsonl + verify-chain.py)
- **Fail-closed**: Ambiguous cases → DENY (already enforced via policy-eval.py exception handling)
- **Audit completeness**: Every transition logged (already enforced via governed_tool() wrappers)
- **Trust laundering prevention**: Explanations ≠ canonical claims (currently operational discipline, not code-enforced)
- **Reality tethering**: Claims must be verifiable (currently operational discipline, not code-enforced)

**Gap**: Trust laundering prevention and reality tethering are **claimed invariants** but not yet **code-enforced**. They rely on agent behavior (AGENT_CONTRACT.md) and code review, not policy-eval.py checks.

---

## Implementation Surface (Areas Touched)

The Model Delta Engine framing is **conceptual**, not a feature implementation. However, if adopted as a canonical lens for understanding the system, the following areas would be touched:

### Documentation (Primary Surface)

- **GOVERNANCE_OVERVIEW.md**: Add section explaining governance-layer as instance of Model Delta Engine pattern
- **ATTESTATION_SPEC.md**: Reframe decision records as "state transition attestations" (S → T with verification)
- **RUNBOOK.md**: Add failure attribution taxonomy (6 categories for traceable diagnosis)
- **OPS_CANONICAL.md**: Add "Judgment Zone Reduction" section (continuous improvement goal)
- **AGENT_CONTRACT.md**: Strengthen reality tethering and trust laundering prevention language

### No Code Changes Required

The framing does **not** require changes to:
- **policy-eval.py**: Already implements pattern (tool request → policy evaluation → decision record)
- **MCP server**: Already implements pattern (governed tool invocations)
- **verify-chain.py**: Already validates audit trace integrity

### Potential Extensions (If Framing Adopted)

If the Model Delta Engine framing were adopted as canonical, future work could include:

1. **Decision record compression**: Add tooling to compact decision-chain.jsonl into summary packets without losing audit safety
2. **Cross-team translation**: Add "anchor view" generator that produces stakeholder-appropriate explanations while linking back to canonical records
3. **Schema migration tooling**: Extend pattern to policy upgrades (policy V1 → policy V2 with delta tracking and verification)
4. **Judgment zone metrics**: Add measurement for "judgment reduction over time" (track discretionary decisions vs structural rules)

**Note**: These extensions are **speculative**. They are not part of current governance-layer scope.

---

## Risks and Open Questions

### Risks

1. **Abstraction overhead**: Introducing a new conceptual framing could confuse newcomers who understand "policy enforcement" but not "state transfer under governance."

   **Mitigation**: Keep both framings. Introduce Model Delta Engine as "advanced perspective" in GOVERNANCE_OVERVIEW.md, not as replacement for policy enforcement framing.

2. **Scope creep**: The framing suggests broader applications (decision compression, cross-team translation) that are outside current governance-layer scope. Risk of feature requests for unscoped work.

   **Mitigation**: Mark broader applications as [SPECULATIVE] and explicitly out of scope. Model Delta Engine section should be clearly labeled as conceptual reframing, not roadmap commitment.

3. **Trust laundering via framing itself**: If "Model Delta Engine" becomes a narrative claim without operational backing, it violates its own invariant (trust laundering prevention).

   **Mitigation**: Ground the framing in existing implementation. Show how policy-eval.py already implements S → T pattern. Avoid claiming capabilities that don't exist.

4. **Measurement gap for "judgment reduction"**: The framing claims "continuous improvement toward reduced judgment" but provides no falsifiable metric.

   **Mitigation**: Define measurable proxy: count of explicit judgment events logged vs count of structural rules added. Track ratio over time. If ratio increases (more judgment, fewer rules), goal not met.

### Open Questions

1. **What minimal model representation is sufficient for S and T?**
   - Governance-layer uses: tool request (S) → policy decision + normalized args (T)
   - Is this sufficient for other applications (schema migration, learning)?

2. **How should "unrecognized judgment" be detected?**
   - Current: No detection mechanism. Judgment events logged manually in agent messages.
   - Future: Could add explicit judgment markers in decision records?

3. **How should the system handle retroactive constraint updates?**
   - Example: Policy rule added in Phase 3 invalidates Phase 2 decisions
   - Current: No mechanism for retroactive invalidation
   - Future: Add "constraint versioning" to decision records?

4. **What constitutes adequate verification V for "advance when reality agrees"?**
   - Governance-layer: Policy checks (path allowlists, capability checks)
   - Other applications: What is sufficient verification for schema migration? For learning?

5. **How should failure attribution taxonomy be enforced?**
   - Current: Manual classification in failure playbook (RUNBOOK.md)
   - Future: Structured failure records with required attribution category?

6. **Should broader applications be scoped?**
   - Decision record compression: In scope? Priority?
   - Cross-team translation: In scope? Priority?
   - Schema migration: In scope? Priority?
   - Learning (within-domain uplift): In scope? Priority?

---

## Go / No-Go Criteria

### Go Criteria (Conditions for Adoption as Canonical Framing)

The Model Delta Engine framing should be adopted as canonical if:

1. **Multiple use cases emerge** that fit the S → T pattern (governance-layer + N others)
2. **Shared primitives are identified** that reduce duplication across use cases
3. **Failure taxonomy improves diagnosis** (attribution categories correlate with faster resolution)
4. **Judgment reduction is measurable** (falsifiable metric exists and shows improvement)
5. **Trust laundering risk is mitigated** (framing grounded in implementation, not aspiration)

**Threshold**: If 3+ of these conditions are met, the framing provides clear conceptual value.

### No-Go Criteria (Conditions for Rejection as Canonical Framing)

The Model Delta Engine framing should NOT be adopted if:

1. **Only governance-layer fits the pattern** (no other use cases emerge) → framing is premature generalization
2. **Abstraction confuses more than clarifies** (newcomers struggle with S/T/M/G/D terminology)
3. **No measurable improvement** (failure diagnosis times unchanged, judgment zone stable)
4. **Scope creep occurs** (feature requests for unscoped applications based on framing)
5. **Trust laundering detected** (framing becomes narrative claim without operational backing)

**Current Assessment**:
- **Pro adoption**: Governance-layer already implements the pattern operationally
- **Con adoption**: No other use cases yet demonstrated; broader applications are speculative
- **Risk**: Abstraction overhead and scope creep

**Recommendation**: **Adopt framing as [SPECULATIVE] perspective**, not as canonical lens. Include in GOVERNANCE_OVERVIEW.md as "Model Delta Engine Framing" section with explicit [SPECULATIVE] tag. Monitor for:
- Additional use cases that fit S → T pattern
- Measurable improvements in failure diagnosis
- Judgment zone reduction metrics

If evidence accumulates, upgrade from [SPECULATIVE] to [IMPLEMENTED]. If no evidence after 6 months, deprecate as premature generalization.

---

## Status and Next Steps

**Status**: [SPECULATIVE]

The framing is conceptually coherent and governance-layer already implements the pattern for tool execution. However, broader applications (decision compression, cross-team translation, schema migration, learning) remain unproven.

**Proposed Next Steps** (if framing adopted):

1. **Add Model Delta Engine section to GOVERNANCE_OVERVIEW.md** [SPECULATIVE]
   - Position governance-layer as instance of broader pattern
   - Map S/T/M/G/D/P/V to policy-eval.py implementation
   - Mark broader applications as speculative and out of scope

2. **Add failure attribution taxonomy to RUNBOOK.md** [SPECULATIVE]
   - 6 categories: Mapping Error, Missing Constraint, Wrong Dependency Ordering, Insufficient Verification, State Misrepresentation, Unrecognized Judgment
   - Usage pattern: symptom → trace → classify → resolve → document

3. **Add "Judgment Zone Reduction" section to OPS_CANONICAL.md** [IN_PROGRESS]
   - Goal: continuous improvement toward reduced judgment
   - Mechanisms: evidence accumulation, structural differentiation, constraint refinement
   - Non-goal: judgment zone will never be zero

4. **Add reality tethering language to AGENT_CONTRACT.md** [IMPLEMENTED]
   - "If not true to reality as operationally knowable, it is wrong"
   - Trust laundering prevention strengthened
   - "Advance when reality agrees" as canonical phrase

**Blockers**: None. Framing can be adopted incrementally via documentation additions. No code changes required.

**Risks to Monitor**:
- Abstraction overhead (newcomer confusion)
- Scope creep (feature requests for speculative applications)
- Trust laundering (framing becomes narrative claim)
- Measurement gap (judgment reduction not falsifiable)

**Decision Point**: After 6 months, evaluate:
- Has another use case emerged that fits S → T pattern?
- Has failure diagnosis improved measurably?
- Has judgment zone shrunk measurably?

If yes to 2+, upgrade to [IMPLEMENTED]. If no to all, deprecate as premature generalization.
