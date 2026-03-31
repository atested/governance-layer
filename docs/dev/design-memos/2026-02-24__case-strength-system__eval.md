# Evaluation Memo: Case Strength - Real-Time Governed Evaluation & Visualization

**Date**: 2026-02-24
**Status**: [SPECULATIVE]
**Evaluator**: Cecil (governance operator)

---

## What It Is

**Case Strength** is a governance-backed system that evaluates how well an argument supports itself structurally in real time, without claiming to determine truth. It converts reasoning (speech or text) into argument graphs, scores structural support along a constraint continuum, generates charitable counter-cases, and visualizes the result to avoid "authority illusion."

**Core components**:
- Argument graph parser (text/speech → structured claims + supports)
- Constraint continuum scorer (speculation → assumption → evidence → formal derivation)
- Counter-case generator (charitable opposition)
- Sensitivity analyzer (essential premises vs non-essential supports)
- Decay modeler (time-based freshness)
- Interactive visualizer (premise toggling, shadow flip, wave metaphor)
- Governance layer (deterministic scoring, replayable logs, auditable transformations)

**Surface display**:
- **Categories**: Weak, Moderate, Strong, Contested
- **Indicators**: Sensitivity, Opposing Case Strength, Freshness
- **Interactive**: Premise disable, shadow flip, structural collapse visualization

**Canonical framing**: *"Structure, not truth."* Measures how tightly reasoning holds together under scrutiny, pressure, and time.

---

## Problem It Solves (Failure Modes)

### Overconfidence in AI-Assisted Reasoning

**Problem**: AI-enabled reasoning sessions create intense flow states that amplify productive thinking but can lead to overconfidence. Well-structured but unsound arguments can feel compelling.

**Failure mode**: User accepts AI-generated reasoning without checking structural dependencies, essential premises, or counter-cases.

**Solution**: Case Strength system makes structural dependencies explicit, always shows opposing case, allows premise toggling to observe collapse.

### Authority Illusion Risk

**Problem**: Any visual scoring system risks being interpreted as "truth meter" rather than structural robustness indicator.

**Failure modes**:
1. Users equate "Strong" with "True"
2. High scores create false confidence
3. Numeric scores become epistemic authority
4. System becomes oracle rather than instrument

**Solution**: Careful psychological framing:
- Label: "Case Strength" (not "Truth Score")
- No numeric composite scores
- Both sides can be "Strong" (signals uncertainty)
- Always show opposing case
- Interactive premise toggling reinforces conditionality
- Avoid superlatives and absolute language

### Straw-Man Counter-Generation

**Problem**: Systems that generate counter-arguments often create weak opposition to make primary case look stronger.

**Failure mode**: User defeats weak counter and gains false confidence.

**Solution**: Charitability scoring rewards realistic opposing argument representation. Refuting strong counters increases Case Strength more than refuting weak ones.

### Static Reasoning Artifacts

**Problem**: Arguments created at time T may become stale as new evidence emerges, but nothing signals this.

**Failure mode**: Outdated reasoning treated as current without re-evaluation.

**Solution**: Decay modeling causes support to fade over time unless refreshed. Different node types decay at different rates (speculation faster than formal derivation).

---

## Fit with Governance Layer NOW

### Conceptual Fit (High)

The Case Strength system shares governance-layer's core philosophy:
- **Deterministic evaluation**: Same inputs → same scores (like policy-eval.py)
- **Replayable logs**: Every score traceable to transformation steps (like decision-chain.jsonl)
- **Auditable transformations**: Argument graph → Case Strength score must be verifiable
- **No black boxes**: Structural dependencies explicit, not hidden
- **Fail-closed on ambiguity**: Suspension mode when structural anomalies detected

**Philosophical alignment**: Both systems instrument processes without claiming truth. Governance-layer verifies operational constraints; Case Strength verifies structural constraints.

### Technical Fit (Low-Medium)

**Overlap with existing primitives**:
- ✓ Deterministic scoring engine pattern (policy-eval.py)
- ✓ Append-only log pattern (decision-chain.jsonl)
- ✓ Hash-chained records (record_hash, prev_record_hash)
- ✓ Replay verification (verify-chain.py)
- ✗ Argument parsing (not present)
- ✗ Graph analysis (not present)
- ✗ Counter-generation (not present)
- ✗ Visualization layer (not present)

**Reuse potential**: Governance-layer could provide audit backbone for Case Strength scoring, but most components would be net new.

### Scope Fit (Poor)

**Governance-layer current scope**: Tool execution governance for AI coding agents
- Filesystem operations (FS_READ, FS_WRITE, FS_MOVE, FS_DELETE)
- Policy evaluation before tool execution
- Decision records with tamper-evident chains
- Merge protocol enforcement

**Case Strength scope**: Reasoning instrumentation and visualization
- Argument parsing and graph construction
- Structural scoring along constraint continuum
- Counter-case generation
- Interactive visualization
- Meta-cognitive support for long reasoning sessions

**Overlap**: Both use deterministic scoring and audit trails, but domains are orthogonal (tool execution vs reasoning structure).

**Assessment**: Case Strength is a **separate application** that could use governance-layer patterns, not an extension of governance-layer's current mission.

### Reuse Map: Governance-Layer Primitives → Case Strength

If Case Strength were built as a separate application, it could reuse the following governance-layer patterns:

| Governance-Layer Primitive | Case Strength Reuse | Adaptation Required |
|---|---|---|
| **Attestation pattern** (policy records) | Case Strength evaluation records | Adapt schema: tool request → argument graph input; policy decision → Case Strength score |
| **Evidence bundles** (TESTS.txt with [exit=N]) | Argument evaluation transcripts | Adapt format: test outputs → scoring steps, premise toggles, counter-generation logs |
| **Reason codes** (RC-FS-PATH-DISALLOWED, etc.) | Structural anomaly codes | Define new taxonomy: SC-CIRCULAR-REASONING, SC-ESSENTIAL-PREMISE-INVALID, etc. |
| **Replay verification** (verify-chain.py) | Case Strength score replay | Same pattern: re-execute scoring from logged inputs, verify determinism |
| **Time ribbon rendering** (EPIC design) | Decay visualization | Adapt: decision chain timestamps → argument freshness decay curve |
| **Hash chaining** (record_hash, prev_record_hash) | Evaluation chain integrity | Same pattern: link evaluation records, detect tampering |
| **Deterministic normalization** (canonical paths, sorted args) | Canonical argument representation | Adapt: filesystem paths → claim IDs, support edges |
| **Fail-closed posture** | Suspension mode | Same principle: ambiguous structure → halt scoring, emit anomaly code |
| **Governed tool wrappers** | Governed evaluation functions | Same pattern: all scoring operations log inputs/outputs before returning |

**Key insight**: Governance-layer provides **audit backbone** pattern (deterministic scoring + replayable logs + tamper evidence), but Case Strength would need to implement **domain logic** (argument parsing, graph analysis, counter-generation) from scratch.

**Effort saved by reuse**: ~10-15% (governance backbone patterns exist). Remaining 85-90% is net new development (argument-specific components).

---

## Implementation Surface (If Pursued as Separate Application)

### Core Components (New Development)

1. **Argument Parser**:
   - Input: Text, speech-to-text, structured format
   - Output: Claim graph with support relationships
   - Challenge: Natural language understanding, claim extraction, support linking
   - Estimated effort: Large (4-6 months)

2. **Constraint Continuum Scorer**:
   - Input: Claim graph with node types (speculation, assumption, evidence, formal)
   - Output: Per-node constraint scores, aggregate Case Strength
   - Challenge: Deterministic scoring rules, essential premise detection, diminishing returns calculation
   - Estimated effort: Medium (2-3 months)

3. **Counter-Case Generator**:
   - Input: Primary argument graph
   - Output: Charitable counter-argument graph
   - Challenge: Identifying attack vectors, avoiding straw-man, charitability measurement
   - Estimated effort: Large (4-6 months)

4. **Sensitivity Analyzer**:
   - Input: Argument graph with user-disabled premises
   - Output: Recalculated Case Strength, structural collapse visualization
   - Challenge: Dependency propagation, essential vs non-essential distinction
   - Estimated effort: Medium (2-3 months)

5. **Decay Modeler**:
   - Input: Argument graph with timestamps
   - Output: Freshness-adjusted scores
   - Challenge: Decay rate calibration, time-based recalculation triggers
   - Estimated effort: Small-Medium (1-2 months)

6. **Interactive Visualizer**:
   - Input: Case Strength scores, argument graph, counter-case
   - Output: Visual display with wave metaphor, premise toggles, shadow flip
   - Challenge: Psychological framing, avoiding authority illusion, three-second comprehension goal
   - Estimated effort: Large (4-6 months)

7. **Governance Backbone** (Could Reuse):
   - Input: Evaluation requests
   - Output: Deterministic score records with hashes, replayable logs
   - Challenge: Adapting policy-eval.py pattern to argument scoring
   - Estimated effort: Small (governance-layer patterns exist)

**Total estimated effort**: ~18-30 months for full implementation (rough order-of-magnitude, application-level estimate, not governance-layer work)

### Documentation (If Integrated)

- **New document**: CASE_STRENGTH_SPEC.md (scoring rules, constraint continuum, counter-generation)
- **New document**: CASE_STRENGTH_VISUALIZATION.md (UI principles, authority illusion mitigation)
- **Enhancement**: GOVERNANCE_OVERVIEW.md (add Case Strength as application example)

### No Changes to Governance-Layer Core

**Important**: Pursuing Case Strength would **not** require changes to existing governance-layer primitives (policy-eval.py, MCP server, verification tools). It would be a parallel application that reuses patterns.

---

## Risks and Open Questions

### Risks

1. **Authority illusion despite framing**: Users may still interpret "Strong" as "True" regardless of messaging.

   **Mitigation**: User testing required. A/B test different labels ("Case Strength" vs "Structural Support" vs "Argument Tightness"). Measure misinterpretation rate.

2. **Complexity vs simplicity tension**: System has many components (decay, charitability, sensitivity, counters) but must be understood in three seconds.

   **Mitigation**: Progressive disclosure. Surface view shows 4 categories (Weak/Moderate/Strong/Contested). Advanced view exposes sensitivity, decay, charitability. Default to simple.

3. **Deterministic scoring impossibility**: Natural language arguments may not have deterministic constraint scores without human judgment.

   **Mitigation**: Accept judgment zones. Log discretionary decisions explicitly. Use ranges instead of point scores. Mark "Contested" when determinism breaks down.

4. **Counter-generation quality**: Weak or straw-man counters undermine entire system value.

   **Mitigation**: Charitability scoring with external validation. Gold-standard counter-case corpus. Human-in-the-loop counter review for high-stakes use.

5. **Decay calibration**: Wrong decay rates could make system too aggressive (everything stale quickly) or too passive (nothing decays).

   **Mitigation**: Empirical calibration. Different domains may need different rates. User-adjustable decay sensitivity.

6. **Scope creep from governance-layer mission**: Pursuing Case Strength diverts effort from tool execution governance.

   **Mitigation**: Treat as separate project with separate repo if pursued. Governance-layer remains focused on tool execution.

### Open Questions

1. **What is the minimum viable surface indicator set?**
   - Current proposal: Category (4 levels), Sensitivity, Opposing Case Strength, Freshness
   - Alternative: Just Category + "Contested" flag?
   - Trade-off: Nuance vs three-second comprehension

2. **How should "Strong" be communicated without creating authority illusion?**
   - Options: "Structurally Strong", "Tightly Supported", "Well-Built", "Stable"
   - User testing required to measure psychological loading

3. **How prominently should decay be displayed?**
   - Aggressive: Decay bar always visible, fading color intensity
   - Moderate: Freshness indicator in secondary position
   - Passive: Only show when decay significant
   - Risk: Too prominent → users think system wants refresh; too hidden → stale reasoning unnoticed

4. **How does charitability scoring work deterministically?**
   - Measure counter-case structural depth?
   - Compare to human-rated gold standard?
   - Detect straw-man patterns algorithmically?

5. **What triggers Suspension Mode?**
   - Circular reasoning detected?
   - Contradictory premises?
   - Essential premise invalidated?
   - Definition unclear without implementation

6. **Can two "Strong" cases coexist without confusing users?**
   - Design goal: Signal uncertainty, not truth
   - Risk: Users expect system to pick winner
   - Mitigation: "Contested" label + visual divergence indicator

7. **What happens to governance-layer if Case Strength pursued?**
   - Separate project? Same repo? Shared primitives?
   - Risk of governance-layer becoming general-purpose reasoning platform

---

## Go / No-Go Criteria

### Go Criteria (Conditions for Pursuing as Separate Application)

Case Strength should be pursued if:

1. **High-stakes reasoning common**: Users frequently make important decisions based on AI-assisted reasoning
2. **Overconfidence observed**: Current tools amplify flow state but lack structural awareness
3. **Authority illusion solvable**: User testing shows framing successfully prevents truth-meter interpretation
4. **Counter-generation feasible**: Technical path exists for charitable counter-case generation
5. **Governance patterns valuable**: Deterministic scoring + audit trails provide defensibility users need
6. **Separate team available**: Governance-layer team can remain focused on tool execution while separate team builds Case Strength

**Threshold**: If 4+ conditions met and authority illusion risk is manageable, Case Strength provides clear value.

### No-Go Criteria (Conditions for Rejection)

Case Strength should NOT be pursued if:

1. **Authority illusion unsolvable**: Users consistently interpret "Strong" as "True" despite framing
2. **Counter-generation too weak**: System produces straw-man opposition, undermining credibility
3. **Scope drift from governance-layer**: Building Case Strength would derail tool execution governance mission
4. **Three-second comprehension impossible**: Surface view too complex for casual users
5. **Deterministic scoring infeasible**: Argument structure evaluation requires too much human judgment
6. **Existing tools sufficient**: Current reasoning aids (notebooks, diagrams, peer review) already mitigate overconfidence adequately

**Current Assessment**:

**Pro pursuit**:
- Problem is real (overconfidence in AI reasoning)
- Philosophical alignment with governance-layer (determinism, audit, no truth claims)
- Novel framing ("Structure, not truth") may solve authority illusion

**Con pursuit**:
- Massive scope (18-30 months full implementation)
- Technical unknowns (counter-generation quality, deterministic scoring feasibility)
- Authority illusion risk remains (no user testing yet)
- Orthogonal to governance-layer mission (tool execution vs reasoning instrumentation)

**Recommendation**: **Do not pursue as governance-layer extension**. If Case Strength is valuable, pursue as **separate application** with separate repo that may reuse governance-layer patterns (deterministic scoring, audit logs).

**Rationale**:
1. Governance-layer should remain focused on tool execution governance (current mission)
2. Case Strength requires net new components (parser, graph, counter-gen, viz) with minimal primitive reuse
3. Authority illusion risk requires extensive user testing before committing resources
4. 18-30 month timeline would dominate governance-layer roadmap

**Alternative**: Document Case Strength as **example application** of governance patterns in APPLICATIONS_INDEX.md. Treat as design exploration, not implementation commitment.

---

## Status and Next Steps

**Status**: [SPECULATIVE]

Case Strength is a well-defined concept with clear problem statement, design principles, and component architecture. However, it remains speculative relative to governance-layer's current scope.

**If pursuing as separate application** (decision required):

1. **User testing**: Validate authority illusion mitigation
   - Test labels: "Case Strength" vs alternatives
   - Test framing: "Structure not truth" messaging
   - Measure misinterpretation rates
   - Goal: <10% interpret "Strong" as "True"

2. **Technical feasibility study**: Counter-generation
   - Prototype charitable counter-case generator
   - Measure charitability vs human gold standard
   - Identify straw-man failure modes
   - Goal: >80% charitability score vs human counters

3. **Minimal viable prototype**: Single-argument scoring
   - Build constraint continuum scorer
   - Test deterministic scoring feasibility
   - Measure scoring consistency (same input → same score)
   - Goal: >95% determinism

4. **Governance backbone reuse study**:
   - Adapt policy-eval.py pattern to argument scoring
   - Implement decision-chain.jsonl equivalent for case evaluations
   - Measure audit trail completeness
   - Goal: 100% replayable evaluations

**If documenting as example only** (recommended):

1. **Add to APPLICATIONS_INDEX.md**:
   - Case Strength as governance pattern application
   - Speculative status
   - Link to design memo

2. **Reference in GOVERNANCE_OVERVIEW.md**:
   - "Broader Applications" section
   - "State transfer pattern extends beyond tool execution"
   - Mark [SPECULATIVE]

**Blockers**: None for documentation. For implementation, blockers are:
- Authority illusion user testing
- Counter-generation feasibility study
- Deterministic scoring validation
- Scope approval (separate project vs governance-layer extension)

**Risks to Monitor**:
- Authority illusion (users interpret scores as truth)
- Complexity (three-second comprehension requirement)
- Counter-generation quality (straw-man failure)
- Decay calibration (too aggressive or too passive)
- Scope drift (from tool governance to reasoning platform)

**Decision Point**: After user testing + technical feasibility studies (6-9 months), evaluate:
- Can authority illusion be mitigated to acceptable level?
- Is counter-generation quality sufficient?
- Is deterministic scoring feasible?

If yes to all three, Case Strength could be viable as separate application. If no to any, concept remains speculative.

---

## Assessment: Case Strength vs Governance Layer

**Relationship**: Conceptual alignment, minimal technical overlap, orthogonal scopes.

| Dimension | Governance Layer | Case Strength |
|---|---|---|
| **Mission** | Tool execution governance | Reasoning instrumentation |
| **Domain** | Filesystem, shell, web | Argument structure |
| **Inputs** | Tool requests with intent | Text, speech, argument graphs |
| **Outputs** | Policy decisions (ALLOW/DENY) | Case Strength scores (Weak/Moderate/Strong/Contested) |
| **Evaluation** | Path allowlists, capability checks | Constraint continuum, premise dependencies |
| **Audit** | Decision chain with hashes | Evaluation log with structural transformations |
| **Determinism** | Normalized args, canonical paths | Constraint scoring rules, decay models |
| **Status** | [IMPLEMENTED] operationally | [SPECULATIVE] concept |

**Overlap**: Both use deterministic scoring + audit patterns. Governance-layer could provide audit backbone for Case Strength.

**Divergence**: Case Strength requires net new components (argument parsing, graph analysis, counter-generation, visualization) with no governance-layer equivalents.

**Recommendation**: If valuable, pursue Case Strength as **separate application** that reuses governance patterns. Do not extend governance-layer scope to include reasoning instrumentation.

**Next step**: Document as speculative example application in APPLICATIONS_INDEX.md. Defer implementation decision pending user testing and feasibility studies.
