# Residual Discretion Doctrine

**Status**: [CANDIDATE] — pressure-testable doctrine artifact, not yet canonical
**Date**: 2026-03-08 (fifth revision)
**Author**: Greg Keeter
**Working name history**: Originally "Earned Grace" (placeholder, 2026-03-06). Renamed "Doctrine of Residual Discretion" (2026-03-06). Finalized as "Residual Discretion Doctrine" (2026-03-08).

---

## Boundary Objective

The system must compress discretion into the smallest defensible remainder and must locate the boundary between deterministic resolution and residual discretion as precisely as the problem domain allows.

Wherever deterministic resolution is available, it is obligatory. Where deterministic resolution is insufficient, the system must diagnose the insufficiency, classify it, and select a governed disposition before any terminal discretion is admitted. The deterministic surface must grow over time through governed structural feedback. The residual non-deterministic surface must shrink correspondingly.

---

## A. LANGUAGE DISCIPLINE

### Purpose

This section governs how language is drafted and interpreted in this doctrine. Its purpose is to reduce interpretive discretion and to prevent judgment from entering the doctrine through ambiguous wording. Language discipline is not stylistic preference; it is a structural requirement for a document whose function is to constrain what the system may and may not do.

### Drafting rules

1. **One canonical term per core concept.** Each architectural concept must have exactly one term. Synonyms must not be used interchangeably. Where a term is defined in Section 3, that term is the only admissible way to refer to the concept throughout this document.

2. **Constraint language over descriptive language.** Where a statement establishes what the system must or must not do, it must use constraint language ("must," "must not," "is limited to"). Descriptive language ("is designed to," "aims to," "is intended to") must not be used where a binding constraint is meant.

3. **No undefined discretionary terms in deterministic sections.** Sections describing Pass (Level 1) must not contain terms that imply discretion, interpretation, or judgment (e.g., "appropriate," "reasonable," "adequate," "sufficient" without explicit criteria). Where such terms appear, they must be accompanied by explicit, deterministic criteria.

4. **State exclusions where category boundaries matter.** When defining what a category includes, state what it excludes if the boundary is load-bearing. Omission of exclusions at category boundaries is a drafting defect.

5. **Prefer strong boundary language.** When closing a loophole or preventing category drift, use "must," "must not," or "is limited to" rather than "should," "should not," or "is expected to."

### Interpretation of modal terms

The following terms have fixed meanings throughout this document:

- **"must"**: Obligatory. Violation constitutes a doctrine breach. No exception unless the doctrine itself provides one.
- **"must not"**: Prohibited. The act is a doctrine breach regardless of intent or outcome.
- **"is limited to"**: The enumerated scope is exhaustive. Anything outside the enumeration is prohibited.
- **"may"**: Permitted but not required. The act is within the system's discretion, subject to any stated conditions.
- **"should"**: Recommended but not obligatory. Departure is permitted if the reason is stated and recorded. Used only where the doctrine identifies a strong default that may have legitimate exceptions.
- **"will"**: Descriptive of expected system behavior under normal operation. Not a constraint; used only for describing architectural flow.

Terms not on this list carry no special doctrinal weight and must not be read as implying constraint or permission beyond their ordinary meaning.

---

## 1. PURPOSE

### What problem this doctrine solves

The governance layer currently has two modes: deterministic resolution (ALLOW/DENY) and implicit human authority (Greg decides). The space between them is unstructured. When policy evaluation cannot resolve a case, there is no governed path for what follows. Cases fall through to ad hoc human decision without diagnosis, without classification of why determinism was insufficient, and without feedback into the deterministic surface.

This creates three problems:

1. **Premature discretion.** Difficult cases bypass the system rather than improving it.

2. **Invisible non-determinism.** When decisions involve judgment, there is no record distinguishing them from deterministic evaluation. The audit trail cannot identify which decisions were computed and which were chosen.

3. **Erosion of the deterministic surface.** Without structural protection, convenience pressure gradually moves cases from deterministic resolution to discretion. The system's core asset — deterministic, replayable evaluation — degrades silently.

### Why the project needs it now

The project's deterministic core is stable: policy evaluation, attestation, replay, signing. The next architectural question is not "how do we make determinism work?" but "what governs the space where determinism ends?" Deferring this question allows the unstructured space to grow and ad hoc patterns to calcify into de facto architecture.

### Continuity, not departure

This doctrine is a continuation of the project's original deterministic-first orientation. The governance layer was built on the premise that deterministic, replayable, tamper-evident evaluation is the foundation of trustworthy tool execution. This doctrine extends that premise into the space where determinism is insufficient: the same values — precision, auditability, structural honesty — must govern what replaces it. It also governs how the system learns and grows: structural feedback is the mechanism by which the deterministic surface expands, and it is itself governed.

### Why this is not a naming exercise

The doctrine establishes concrete architectural commitments: a three-level decision architecture with a one-way flow constraint, a hybrid diagnostic-and-routing layer, typed output categories with explicit admission conditions and exclusions, invariants protecting the deterministic surface, a governed structural feedback function, a distinction between replayable and auditable attestation, and a feedback loop for deterministic surface expansion. These are structural commitments, not rhetorical framing.

---

## 2. CORE PRINCIPLE

Deterministic resolution is obligatory wherever deterministic basis exists. Where the current deterministic basis is insufficient to produce a determinate ALLOW or determinate DENY, the system must diagnose the insufficiency, classify it, and select a governed disposition before any terminal discretion is admitted. Terminal discretion is the residual remainder after deterministic evaluation and structured diagnostic triage have been completed and recorded. The system must locate the boundary where determinism ends, as precisely as possible, and must push that boundary outward through governed structural feedback.

Four operative parts:

1. **Exhaustion.** Deterministic evaluation must be performed first. Pass is the sole deterministic resolver; no other level may perform deterministic resolution.
2. **Diagnosis.** Insufficiency of determinism must be classified: is this residual uncertainty, or a structural deficiency? Diagnosis is itself a form of judgment (diagnostic judgment), distinct from the terminal case-resolution judgment it may ultimately authorize.
3. **Admission.** Terminal discretion enters only through a governed gate, after diagnostic triage, with recorded provenance. The Triage classification constrains what terminal discretion may do.
4. **Contraction.** The non-deterministic surface must shrink over time. Structural feedback converts diagnostic findings, recurring patterns, and outcome feedback into deterministic surface expansion. Contraction is governed, not autonomous.

---

## 3. DEFINITIONS

**Pass (Level 1)**: The sole deterministic resolver. Pass is limited to deterministic evaluation of explicitly specified inputs, prerequisites, mappings, and decision criteria. Pass must not rely on inferred adequacy, implied completeness, discretionary sufficiency judgments, or any other non-deterministic assessment. Pass includes completeness and sufficiency checking; all such criteria must be explicitly defined and deterministic. Pass produces ALLOW, DENY, or UNDECIDED. Where the specified conditions do not support a determinate ALLOW or determinate DENY, Pass must emit UNDECIDED.

**Triage (Level 2)**: The diagnostic and routing layer. Triage receives UNDECIDED from Pass and determines why the current deterministic basis was insufficient, classifies all failure conditions present, selects the admissible disposition, and emits structural signals where appropriate. Triage is a hybrid layer: it must exhaust deterministic classification wherever feasible before crossing into judgment. A deterministic Triage act may include identifying structural deficiency and emitting a structural signal. Where deterministic criteria do not fully suffice, Triage applies the minimum necessary governed judgment. Triage must not resolve cases. Triage must not complete rules, create precedent, or perform deterministic resolution of any kind.

**Terminal Judgment (Level 3)**: The layer that exercises terminal case-resolution discretion. Level 3 is reachable only when Triage has classified the governing condition as genuine residual uncertainty and has selected a specific terminal judgment method as the admissible exit. Level 3 is limited to applying the method Triage selected.

**Deterministic resolution**: A decision pathway where the same well-defined inputs produce the same output on every evaluation. The output is computable from explicitly specified rules, facts, mappings, and constraints without discretion.

**UNDECIDED**: An internal transfer state emitted by Pass when the current deterministic basis is insufficient to produce a determinate ALLOW or determinate DENY. UNDECIDED is never an external-facing output. It is part of the fail-closed architecture: only a determinate ALLOW opens the gate; a determinate DENY closes it; everything else remains closed and transfers internally to Triage. Triage is part of the fail-closed architecture, not an exception to it.

**Deterministic insufficiency**: A condition surfaced by Pass when evaluation encounters gaps in its own basis — missing rules, undefined precedence, unmapped case structure — that prevent it from reaching a determinate ALLOW or determinate DENY. Pass may surface deterministic insufficiencies during evaluation even after initial completeness checking has passed. Whether a given insufficiency reveals a structural defect is Triage's determination, not Pass's.

**Diagnostic judgment**: The form of judgment exercised by Triage. It includes failure classification, concurrent-condition identification, governing-condition determination, admissible-exit selection, and self-assessment of whether each act was performed on deterministic or judgmental grounds. Its object is the *structure of the insufficiency*, not the *resolution of the case*.

**Terminal judgment**: The form of judgment exercised by Level 3. Its object is the case itself. Terminal judgment is authorized only after Triage has classified the insufficiency, confirmed genuine residual uncertainty as the governing condition, and selected a specific terminal judgment method as the admissible exit.

**Residual uncertainty**: Genuine undecidability that persists after Triage has diagnosed the insufficiency and confirmed it is not caused by a structural deficiency in the system. The case is legitimately outside the reach of current deterministic structure.

**Structural deficiency**: An UNDECIDED outcome that Triage diagnoses as caused by a defect in the system's own structure: a rule gap, a rule conflict, an avoidable ambiguous mapping, a missing meta-policy, or an underbuilt prerequisite. Structural deficiencies are not legitimate terminal judgment cases. They are inputs to the Structural Feedback Function.

**Admissible non-resolution**: The determination that no party — system or human — should resolve this case at this time. Non-resolution is a first-class governed output, not a failure. Its basis must be stated.

**Structural signal**: An output of Triage indicating that the deterministic surface has a structural deficiency. The signal must identify the deficiency class and the case that exposed it. Structural signals may be emitted alongside any other disposition when concurrent findings include both structural deficiencies and a separate governing condition. Processing a structural signal is the responsibility of the Structural Feedback Function, not of the current decision process.

**Concurrent findings**: Multiple independent failure conditions co-occurring in a single case. Each finding must be classified independently. Structural signals must be emitted for all structural deficiencies found, regardless of which condition governs the case's immediate disposition.

**Deterministic surface**: The set of cases that the system can resolve deterministically at a given point in time, defined by its current rules, facts, mappings, and constraints. The deterministic surface must grow over time through governed structural feedback.

**Residual non-determinism boundary**: The boundary between cases resolvable deterministically and cases requiring discretion or non-resolution. The doctrine's objective is to locate this boundary as precisely and as far outward as the problem domain allows.

**Structural Feedback Function**: The governed process that gathers and processes approved signals, identifies recurring issues and structural opportunities, surfaces candidate changes, and supports governed modification decisions. It proposes and informs. It must not autonomously modify the system. Structural modification is limited to changes reviewed and approved by the product owner and governance operator.

**Structural Feedback Packet**: A bounded, opt-in artifact generated by the Structural Feedback Function. It summarizes system-performance patterns, recurring insufficiencies, escalation trends, and structural improvement candidates. It must not expose specific case data. It is not a self-modification channel and must not be used as one.

---

## 4. THREE-LEVEL ARCHITECTURE

### Level 1: Pass

**Purpose**: The sole deterministic resolver.

**Pass is limited to**: deterministic evaluation of explicitly specified inputs, prerequisites, mappings, and decision criteria. Pass must not rely on inferred adequacy, implied completeness, discretionary sufficiency judgments, or any other non-deterministic assessment.

**Responsible for**:
- Checking completeness and sufficiency of the submission against explicitly defined, deterministic criteria
- Performing deterministic evaluation against current policy
- Producing ALLOW, DENY, or UNDECIDED
- Emitting structured reason codes for DENY outcomes
- Surfacing deterministic insufficiencies encountered during evaluation, including insufficiencies discovered after initial completeness checking has passed

**Not responsible for**:
- Diagnosing why a case is UNDECIDED or whether the insufficiency reveals a structural defect
- Classifying insufficiencies or selecting dispositions
- Exercising any form of judgment or interpretation
- Resolving cases outside its deterministic basis

**Fail-closed rule**: Only a determinate ALLOW opens the gate. A determinate DENY closes it. Everything else — including any case where the current deterministic basis is insufficient to produce a determinate ALLOW or determinate DENY — remains closed and transfers internally as UNDECIDED to Triage.

**Sufficiency constraint**: All completeness and sufficiency criteria applied by Pass must be explicitly defined and deterministic. If a criterion requires interpretation, that interpretation belongs in Triage, not in Pass. Pass must not conceal judgment within sufficiency checking.

### Level 2: Triage

**Purpose**: Diagnose why Pass could not resolve. Classify all failure conditions. Select the admissible disposition. Emit structural signals where appropriate.

Triage is a hybrid layer. It must exhaust deterministic classification wherever feasible before crossing into judgment. A deterministic Triage act may include identifying structural deficiency and emitting a structural signal. Where deterministic criteria do not fully suffice, Triage applies the minimum necessary governed judgment. Triage must identify, for each act it performs, whether that act was performed on deterministic or judgmental grounds.

**Responsible for**:
- Receiving UNDECIDED cases from Pass with the full evaluation context, including any insufficiencies Pass surfaced
- Determining why the current deterministic basis was insufficient to produce a determinate ALLOW or determinate DENY
- Identifying all independent failure conditions present in the case (concurrent findings)
- Classifying each condition into a typed category (Section 5)
- Determining which condition governs the immediate disposition
- Selecting the admissible exit path consistent with the governing condition
- Emitting structural signals for all structural deficiencies found, regardless of which condition governs immediate disposition
- Identifying, for each act performed, whether it was performed on deterministic or judgmental grounds (INV-9)

**Not responsible for**:
- Performing deterministic resolution of any kind
- Completing rules, creating precedent, or acting as a shadow resolver
- Making terminal case-resolution judgments (Level 3's domain, if reached)
- Repeating Pass's evaluation
- Feeding results back to Pass within the same decision process

**Triage must not resolve cases.** If Triage identifies that a structural change would enable future deterministic resolution, it must emit a structural signal and the current decision process must end. Triage must not apply the structural change, must not perform the resolution, and must not create informal precedent. Resolution of the originating case may occur only after an approved structural change has been applied and a new Pass evaluation begins as a new decision process.

### Level 3: Terminal Judgment

**Purpose**: Exercise terminal case-resolution discretion for cases that Triage has classified as genuine residual uncertainty and for which Triage has selected a specific judgment method as the admissible exit.

**Responsible for**:
- Receiving classified residual cases from Triage with the full diagnostic chain
- Applying the resolution method that Triage identified as admissible — and only that method
- Recording the judgment with full provenance: who decided, what they saw, what chain preceded, what rationale was applied
- Distinguishing between judgment sub-modes: bounded estimation, human authority, non-resolution, random tie-break

**Not responsible for**:
- Diagnosing why the case is here (Triage has already classified it)
- Evaluating whether the case should have been resolved deterministically (Triage has already confirmed it cannot be under current structure)
- Operating without a preceding Triage classification and exit-path selection

**Constraint**: Level 3 is reachable only through Triage. It must not be invoked directly. Level 3 is limited to applying the method Triage selected. If Triage classified the governing condition as "bounded estimation justified," Level 3 must apply bounded estimation within the stated bounds; it must not exercise unconstrained judgment.

### One-Way Flow Constraint

The decision process flows in one direction only: Pass → Triage → (Level 3 or governed disposition or structural signal). There must be no live back-and-forth between levels within a single decision process.

If Triage identifies that structural change is needed:
1. Triage must emit a structural signal
2. The current decision process must end
3. The Structural Feedback Function processes the signal separately
4. A new Pass evaluation may begin only after an approved structural change has been applied, as a new decision process

This constraint prevents completion pressure from deforming the architecture, prevents judgment from leaking into deterministic resolution, and ensures that structural changes to the deterministic surface go through governed channels.

### Judgment across levels

The architecture does not claim that Triage is non-judgmental. The operative distinction is the *object and scope* of judgment at each level:

- **Pass**: No judgment. Deterministic evaluation only.
- **Triage (diagnostic judgment)**: Why was the current deterministic basis insufficient? What kind of insufficiency is this? What disposition is admissible? Was each act deterministic or judgmental?
- **Level 3 (terminal judgment)**: Given this classified residual uncertainty, what should the outcome be?

Triage's judgment concerns the *structure and disposition of the insufficiency*. Level 3's judgment concerns the *case itself*. This distinction matters for attestation: diagnostic judgment can be audited against structural evidence (does the classified deficiency actually exist in the system's current structure?), while terminal judgment can be audited only against process integrity and stated rationale.

---

## 5. TRIAGE DOCTRINE

### Why Triage exists

Without Triage, the system has two responses to insufficiency: deny (fail-closed) or escalate (ask a human). Denial discards cases that might be resolvable with diagnosis and misses structural feedback opportunities. Escalation externalizes work the system should be doing — specifically, determining *why* its own deterministic basis was insufficient.

Triage closes this gap. It converts "the current deterministic basis is insufficient" into "the current deterministic basis is insufficient *because*..." and determines what follows from the specific kind of insufficiency.

### What Triage must classify

Triage must distinguish at minimum:

1. **Rule gap**: No rule addresses this case. The deterministic surface has a hole.
2. **Rule conflict**: Multiple rules apply and produce contradictory outcomes.
3. **Ambiguous mapping**: The case maps to the rule structure in more than one defensible way, and the mapping choice changes the outcome.
4. **Missing meta-policy**: Rules exist but no rule governs how to apply them in this configuration (e.g., precedence is undefined).
5. **Insufficient information**: The case cannot be evaluated because required inputs are missing or unverifiable — the rules are not deficient; the inputs are.
6. **Genuine residual**: The rules are complete and consistent for this domain, the inputs are sufficient, but the case involves irreducible uncertainty, value judgment, or authority that deterministic structure cannot provide.

Categories 1–4 are structural deficiencies. Category 5 is an information-gap deferral. Category 6 is the only category that legitimately reaches Level 3 terminal judgment.

No other category may be used to route a case to Level 3.

### Concurrent findings

A case may exhibit multiple independent failure conditions simultaneously.

Triage must:
- Identify all independent conditions, not only the first encountered or the most obvious
- Classify each condition independently
- Emit structural signals for all structural deficiencies found, regardless of which condition governs immediate disposition
- Determine which condition governs the immediate disposition
- Record the full set of findings, not only the governing condition

Structural signals are not contingent on the case's resolution path.

### How Triage distinguishes residual uncertainty from structural deficiency

The test: *could a feasible structural change to the deterministic surface resolve this class of case in the future?*

- If yes → structural deficiency. The system's inability to resolve is a defect.
- If no → residual uncertainty. The case is genuinely outside deterministic reach.
- If unclear → Triage must flag the uncertainty in its diagnostic record rather than silently resolving the classification.

### Triage sufficiency

Triage has completed its work when it has:

1. Identified all independent failure conditions present in the case
2. Classified each as structural deficiency, information gap, or genuine residual
3. Determined which condition governs the immediate disposition
4. Selected an admissible exit path consistent with the governing condition
5. Emitted structural signals for all structural deficiencies found
6. Identified, for each act performed, whether it was on deterministic or judgmental grounds (INV-9)
7. Recorded the full diagnostic chain

Triage is not sufficient merely because it produced a typed output. Perfunctory classification — assigning a category without genuine diagnostic engagement with the case's structural specifics — violates the doctrine.

### What Triage is not

**Triage is not a retry of Pass.** It must not apply the same rules with more effort. Its function is to change the question from "what is the answer?" to "why is the current deterministic basis insufficient, and what follows?"

**Triage is not a shadow deterministic resolver.** It must not complete rules, create one-off precedent, or perform informal resolution under completion pressure. If it identifies that a structural change would enable deterministic resolution, it must emit a structural signal and the current process must end.

**Triage is not non-judgmental.** It exercises diagnostic judgment. What distinguishes it from Level 3 is not the absence of judgment but the object and scope of judgment: the structure of the insufficiency, not the resolution of the case.

---

## 6. TYPED OUTPUT CATEGORIES

The architecture commits to the following output categories. Each is an external-facing disposition produced by Triage or Level 3. UNDECIDED (Pass's internal transfer state) is not among them and must never appear as an external output.

### BOUNDED_ESTIMATION

The case involves uncertainty that can be bounded by structured methods: confidence intervals, range estimates, probabilistic reasoning with declared assumptions.

**Admission conditions** — all must hold:
- The uncertainty must be empirical, quantitative, or otherwise genuinely boundable
- The estimation method must be justified by the classified failure conditions
- The domain of the uncertainty must not be normative, authority-based, or policy-definitional
- Actual bounds must exist and must be stated in the record
- The estimation method and its limitations must be documented

**Exclusions**: Normative questions, authority determinations, policy-definitional choices, and any uncertainty that cannot be bounded are not admissible under this category regardless of how they are framed. If no actual bounds can be stated, the case must not be classified as BOUNDED_ESTIMATION.

### DEFER_INPUT_INSUFFICIENCY

The case cannot be resolved because required inputs are missing or unverifiable. The system's structure is not deficient; the inputs are. Resolution is postponed, not abandoned.

The deferral record must state:
- The specific input gap that prevents resolution
- What information is needed
- From whom or where it is expected

### DEFER_STRUCTURAL_DEFICIENCY

Resolution depends on a structural change to the deterministic surface that has not yet been approved and applied. The current decision process must end. Re-evaluation may begin only after the structural change is in effect, as a new Pass process.

The deferral record must state:
- The structural deficiency identified (linked to the corresponding STRUCTURAL_SIGNAL)
- What structural change is needed

In development and governance contexts, these cases may be placed on hold pending research or structural review. This is primarily a development/governance workflow disposition.

### ESCALATION_JUSTIFIED

The case involves residual uncertainty that requires authority, legitimacy, value judgment, accountability, or information that the system does not possess. Escalation to a specific authority is justified because that authority adds something material the system lacks.

**Admission conditions** — all must hold:
- The material contribution the authority provides must be stated
- The specific authority must be identified
- The preceding diagnostic chain must demonstrate that the governing condition is genuine residual uncertainty, not a structural deficiency

**Exclusions**: "This is hard," "a human should decide," and similar non-specific justifications are not admissible. If the system possesses the same information, authority, and capacity as the proposed escalation target, escalation is not justified.

### NO_ADMISSIBLE_CHOICE

No party — system or human — should resolve this case at this time. All available options violate constraints, the decision would be premature, or the question is ill-formed. Non-resolution is the governed output.

**Admission conditions**:
- The basis for non-resolution must be stated
- The record must identify whether the non-resolution is permanent (the question is ill-formed) or contingent (conditions may change)

### RANDOM_TIEBREAK

The case involves true symmetry: multiple options are equally admissible by all available criteria, and no basis exists for preferring one over another. Random selection is the honest resolution.

**Admission conditions** — all must hold:
- Genuine symmetry must be demonstrated, not merely asserted
- The criteria by which symmetry was assessed must be stated
- The assessment must show that all available criteria were considered

**Exclusions**: Difficulty of comparison is not symmetry. If any criterion distinguishes the options, this category is not admissible.

This category is narrow by design.

### STRUCTURAL_SIGNAL

Triage has identified that the UNDECIDED outcome is caused, in whole or in part, by a structural deficiency in the system: rule gap, rule conflict, ambiguous mapping, missing meta-policy, or underbuilt prerequisite.

The output must identify:
- The deficiency class
- The case that exposed it
- Whether the case has a separate governing condition that permits an independent disposition, or whether the structural deficiency is the sole finding (in which case the disposition is DEFER_STRUCTURAL_DEFICIENCY)

STRUCTURAL_SIGNAL may be emitted alongside any other disposition when concurrent findings include both structural deficiencies and a separate governing condition. The signal is processed by the Structural Feedback Function, not by the current decision process.

---

## 7. STRUCTURAL FEEDBACK FUNCTION

### Purpose

The system's governed mechanism for gathering signals, identifying recurring issues and structural opportunities, surfacing candidate changes, and supporting governed modification decisions. Structural feedback is how the system converts diagnostic findings, recurring patterns, and outcome feedback into candidate deterministic-surface expansions. It is the primary means by which the boundary objective is pursued over time.

### Inputs

The Structural Feedback Function may receive:
- Structural signals from Triage
- Feedback evaluation results (Section 10)
- Recurring insufficiency patterns observed across multiple decision processes
- Recurring escalation, bounded-estimation, no-admissible-choice, and human-judgment patterns
- Approved operational pattern data within its governed observation scope (see OQ-3)

### Responsibilities

- Gathering and processing approved signals and feedback results
- Identifying recurring issues and structural opportunities across cases
- Identifying recurring judgment patterns that indicate opportunities for deterministic expansion
- Surfacing candidate structural changes: rule additions, precedence clarifications, mapping refinements, meta-policy proposals, prerequisite strengthening
- Generating bounded feedback artifacts (Structural Feedback Packets)
- Supporting governed modification decisions with structured evidence

### Exclusions

The Structural Feedback Function must not:
- Resolve originating cases — those decision processes have already ended
- Autonomously modify the system's rules, mappings, meta-policy, or decision criteria
- Generate or apply structural changes without governance review and approval
- Observe operational data outside its governed scope

### Governance posture

The Structural Feedback Function proposes and informs; it must not act. Structural modification of the deterministic surface — adding rules, resolving conflicts, clarifying mappings, defining meta-policy, strengthening prerequisites — is limited to changes reviewed and approved by the product owner and governance operator. This is a deliberate architectural constraint: the function that identifies what should change must not be the function that applies the change.

### Structural Feedback Packet

A bounded, opt-in artifact for deployment contexts. The Structural Feedback Packet summarizes:
- System-performance patterns
- Recurring insufficiencies by deficiency class
- Escalation and judgment trends
- Structural improvement candidates

The Structural Feedback Packet must not expose specific case data. It must not function as a self-modification channel. It must not serve as a user-facing system-control mechanism. Its purpose is limited to supporting post-deployment improvement. Structural modification remains restricted to the product owner and governance operator.

### Relationship to feedback

The Structural Feedback Function and the feedback loop (Section 10) are complementary:
- Feedback evaluation is backward-looking: it assesses past outcomes, process quality, and pattern recurrence
- Structural feedback is forward-looking: it converts feedback findings and structural signals into candidate changes

Feedback identifies opportunities. Structural feedback surfaces proposals. Governance decides.

---

## 8. INVARIANTS

### INV-1: No terminal judgment without prior Pass and Triage

A resolution pathway that invokes terminal case-resolution judgment must be preceded by:
- A Pass evaluation that produced UNDECIDED
- A Triage diagnosis that classified all failure conditions, identified the governing condition as genuine residual uncertainty, and selected a specific terminal judgment method as the admissible exit

Both the Pass evaluation and the Triage classification must be recorded and auditable. Terminal judgment without this chain is ungoverned and constitutes a doctrine breach.

### INV-2: Deterministic surface must not shrink without proving prior structure unsound

If the system currently resolves a class of cases deterministically, that resolution must not be replaced by discretion unless the deterministic path is demonstrated to be unsound: producing incorrect results, relying on false assumptions, or violating invariants. Convenience, complexity, and speed are not grounds for shrinking the deterministic surface.

### INV-3: Recurring insufficiencies and judgment patterns must feed governed structural feedback

When Triage repeatedly classifies similar cases under the same structural-deficiency category, or when feedback evaluation reveals recurring judgment patterns for similar cases, these patterns must be surfaced to the Structural Feedback Function. The system is not meeting this invariant if the same class of insufficiency recurs without generating pressure toward deterministic expansion. This invariant does not require immediate structural change — it requires that recurrence is visible, tracked, and routed to governed structural feedback.

### INV-4: All discretion must be governed, not silent

Every exercise of discretion — diagnostic judgment in Triage, terminal judgment in Level 3, and non-resolution — must produce a decision record with:
- The kind of judgment exercised (diagnostic or terminal)
- The resolution method applied (or the basis for non-resolution)
- The identity and authority of the decider
- The preceding Pass evaluation and Triage classification
- The stated rationale

Silent discretion — resolution without record, or resolution recorded as if deterministic when it is not — constitutes a doctrine breach.

### INV-5: Human escalation must be justified by material contribution

Escalation to human authority is admissible only when the human adds something the system lacks: authority to bind, legitimacy to choose among values, accountability for consequences, or information not available to the system. If the system possesses the same information, authority, and capacity as the human, escalation is not justified.

The justification must be statable and recorded. "This is hard" and "a human should decide" are not admissible justifications.

### INV-6: Judgment and estimation outcomes must generate evaluable records

Every exercise of terminal judgment or bounded estimation must produce a record sufficient for later evaluation of:
- Whether the outcome was correct or defensible in light of subsequent evidence
- Whether process quality was adequate: genuine diagnosis, defensible classification, appropriate method
- Whether luck or circumstances outside the system's control can be distinguished from the quality of the judgment
- Whether the case reveals an opportunity to expand deterministic coverage

Judgment that cannot be evaluated after the fact is judgment the system cannot learn from.

### INV-7: Decision processes are one-way

There must be no live back-and-forth between levels within a single decision process. The flow is Pass → Triage → (Level 3 or governed disposition or structural signal). If structural change is needed, the current decision process must end. A new Pass evaluation may begin only after an approved structural change has been applied, as a new decision process.

### INV-8: Structural changes to the deterministic surface must be governed

Structural changes proposed by the Structural Feedback Function — rule additions, conflict resolutions, mapping clarifications, meta-policy definitions, prerequisite strengthening — are modifications to the system's decision basis. They must be reviewed, approved, and recorded before application. The Structural Feedback Function must not apply changes autonomously.

### INV-9: Triage must identify the basis of each act

For each diagnostic or routing act, Triage must state whether it was performed on deterministic grounds (explicit classification criteria applied) or on judgmental grounds (interpretation or discretion exercised). When Triage exercises judgment, that judgment must be visible in the record as judgment. Judgment must not be concealed behind deterministic-appearing classification.

---

## 9. ATTESTATION AND REVIEW SEMANTICS

### Deterministic outputs (Pass ALLOW/DENY)

**Guarantee**: Replayable. Same inputs must produce the same output on independent re-evaluation.
**Record requirements**: Full input state, policy version, evaluation trace, completeness/sufficiency check results.
**Review semantics**: Verify by replay. If replay produces a different result, the original record is suspect.

### Diagnostic judgment outputs (Triage classifications, exit-path selections)

**Guarantee**: Auditable and structurally verifiable. The classification must be consistent with the structural evidence in the diagnostic chain. The exit-path selection must be consistent with the classified conditions.
**Record requirements**: The UNDECIDED input including any insufficiencies Pass surfaced, the diagnostic reasoning, all classified failure conditions (including concurrent findings), the governing condition, the selected exit path, any structural signals emitted, and for each act whether it was performed on deterministic or judgmental grounds (INV-9).
**Review semantics**: Verify that the classification is consistent with the evidence, that the exit path follows from the classification, and that basis identification is present for each act. A reviewer may disagree with the diagnostic judgment but must be able to see the basis for it. Diagnostic outputs are not required to be deterministically reproducible, but the classification must be defensible given the evidence.

### Terminal judgment outputs (Level 3 decisions)

**Guarantee**: Auditable but not replayable. The decision is recorded with full provenance, but the same inputs may produce a different judgment from a different decider or at a different time.
**Record requirements**: The full preceding chain (Pass evaluation, Triage classification and exit-path selection), the resolution method applied, the decider's identity and authority, the stated rationale.
**Review semantics**: Verify process integrity — was Pass evaluation genuine? Was Triage classification defensible? Was the judgment method consistent with the Triage exit-path selection? Terminal judgment is explicitly exempt from replay verification. Verify against outcome feedback where available (Section 10).

### Structural signal outputs

**Guarantee**: Traceable to the originating case and to specific structural features of the system.
**Record requirements**: Deficiency class, originating case reference, structural features involved, whether the case has a separate governing condition or is deferred pending structural change.
**Review semantics**: Verify that the identified deficiency exists in the system's current structure. Track whether the signal was processed by the Structural Feedback Function, whether it led to a structural change proposal, and whether similar cases recur after any change is applied.

### Structural feedback outputs

**Guarantee**: Traceable to the signals and patterns that motivated them.
**Record requirements**: The structural change proposed, the signal(s) and pattern evidence that motivated it, the governance approval state, and where applicable the before-and-after characterization of the deterministic surface.
**Review semantics**: Verify that the proposed change addresses the identified pattern, that the pattern evidence is real, and that governance approval was obtained before application.

---

## 10. FEEDBACK AND LEARNING

### Why this section is essential

A system that exercises judgment but never evaluates whether that judgment was sound cannot improve. The boundary objective requires evaluation after the fact, not only diagnosis at the point of decision. Without feedback, the system cannot distinguish sound judgment from lucky judgment, cannot identify where deterministic coverage could expand, and cannot assess whether its diagnostic classifications were accurate.

### What feedback the system must generate

For every exercise of terminal judgment or bounded estimation, the system must generate records sufficient to evaluate:

1. **Outcome correctness.** Was the judgment right? Did the bounded estimation fall within its stated bounds?

2. **Process quality.** Was the diagnostic chain genuine? Was the failure classification defensible? Was the selected resolution method appropriate to the classified condition? These are evaluable even when outcome correctness is not yet known.

3. **Luck attribution.** Can circumstances outside the system's control be distinguished from the quality of the judgment?

4. **Deterministic expansion opportunity.** Does this case reveal a pattern capturable by deterministic rules? Repeated judgment of the same kind for similar cases is a signal that the deterministic surface should grow.

### Relationship to feedback evaluation

Feedback evaluation is backward-looking: it assesses past outcomes, process quality, and pattern recurrence. The Structural Feedback Function is forward-looking: it converts feedback findings and structural signals into candidate changes.

The cycle:
1. Pass produces UNDECIDED
2. Triage diagnoses, classifies, selects disposition, emits structural signals
3. Level 3 exercises terminal judgment (if reached)
4. Outcome evidence accumulates
5. Feedback evaluation identifies patterns
6. Structural Feedback Function processes findings and signals, surfaces candidate changes
7. Governance reviews and approves structural changes
8. Approved changes expand the deterministic surface
9. Future cases of the same class are resolved by Pass

This cycle is the system's governed improvement mechanism.

### What feedback does not require

- Real-time evaluation of every judgment — batch or periodic review is acceptable
- Automated correctness assessment — human review is acceptable where automation is infeasible
- Guaranteed outcome data — some judgments may not be evaluable due to missing counterfactuals

The doctrine requires that *records* are generated at decision time so that evaluation is possible when conditions allow.

---

## 11. TERMINATION AND EXHAUSTION

### Legitimate Triage termination

Triage terminates legitimately when it has produced one or more typed outputs from Section 6 covering all identified failure conditions. Legitimate termination requires:

1. All independent failure conditions have been identified
2. Each condition has been classified as structural deficiency, information gap, or genuine residual
3. The governing condition for immediate disposition has been identified
4. The selected exit path is consistent with the governing condition
5. Structural signals have been emitted for all structural deficiencies found
6. Each diagnostic act has been identified as deterministic or judgmental (INV-9)
7. The full diagnostic chain is recorded

Triage does not need certainty in its classifications to terminate legitimately. It needs genuine diagnostic engagement and defensible classifications. If a classification is uncertain, that uncertainty must be part of the record.

### Exhaustion theater

Exhaustion theater is the performance of diagnostic work without genuine diagnostic intent. Indicators include:

- Triage terminates in the same output regardless of failure category
- Triage's classification does not reference specific structural features of the system
- The same failure category is assigned to structurally dissimilar cases
- Concurrent findings are never identified — every case is treated as having a single condition
- Basis identification (INV-9) is uniformly "judgmental" without stating what judgment was exercised or why deterministic classification was insufficient

The doctrine does not prescribe a minimum duration or number of diagnostic steps. It requires that the diagnostic output demonstrate engagement with the specific structural features of the insufficiency. The test: *could a reviewer determine, from the diagnostic record alone, what structural feature of the system caused the UNDECIDED outcome?* If yes, the diagnosis is genuine. If not, it may be theater.

### Open question: formal exhaustion criteria

[OPEN — OQ-1] Whether Triage exhaustion can be verified mechanically or must remain audit-based is not decided. Candidate approaches (structural grounding requirements, sampled audit review, statistical monitoring of output distributions) are identified but none are adopted.

---

## 12. RISKS AND FAILURE MODES

### Exhaustion theater inside Triage

Triage could perform perfunctory diagnosis to reach an escalation or deferral output without genuine engagement. INV-9 (basis identification) provides partial structural defense. But mechanical prevention of theater may not be achievable. This risk may require ongoing audit.

### Soft bypass through UNDECIDED

If Pass produces UNDECIDED too readily, it becomes a path of least resistance routing everything to Triage. UNDECIDED is a precise claim: the current deterministic basis is insufficient to produce a determinate ALLOW or determinate DENY. If Pass produces UNDECIDED for cases its rules should cover, this is itself a structural deficiency that Triage should identify and signal.

### Pseudo-precision about the deterministic/judgment boundary

The three-level structure may imply cleaner separation than reality allows. The concurrent-findings model provides partial mitigation. Triage's classification is explicitly permitted to express uncertainty. But the risk of artificial precision remains.

### Bureaucratic overhead

For ALLOW/DENY cases (the expected majority), the architecture adds no overhead. For genuinely insufficient cases, diagnosis-before-judgment adds process cost. The doctrine does not prescribe Triage duration or complexity — lightweight genuine diagnosis is acceptable. The risk is bounded by the UNDECIDED rate.

### Procedural compliance masking weak judgment

The doctrine governs process, not judgment quality. A fully compliant chain may terminate in a poor decision. Feedback evaluation (Section 10) provides partial mitigation. The doctrine's claim is that governed judgment preceded by diagnosis is better than ungoverned judgment without diagnosis, not that governed judgment is always correct.

### Unjustified escalation as responsibility laundering

Escalation may create an appearance of deference without adding value. INV-5 requires material-contribution justification. The justification must be statable and auditable.

### Feedback loop failure

Records may be generated but never evaluated, or evaluated but findings never consumed, or consumed but the deterministic surface fails to grow. INV-3, INV-6, and INV-8 provide partial structural defense, but none guarantee that the full cycle completes. This is an operational discipline concern the doctrine identifies but cannot fully resolve structurally.

### Structural Feedback Function scope creep

If the Structural Feedback Function accumulates influence as the primary source of structural change proposals, whoever governs its proposal approval effectively controls the system's evolution. The governance posture (proposes and informs, must not act; modification restricted to product owner and governance operator) provides structural mitigation but does not eliminate the institutional concern.

### Hidden judgment in Pass sufficiency checking

If sufficiency criteria in Pass are not fully explicit and deterministic, the completeness check becomes concealed judgment inside a layer that must not exercise judgment. The sufficiency constraint in Section 4 addresses this directly, but the risk requires ongoing vigilance.

---

## 13. RESOLVED QUESTIONS

The following questions, open in prior drafts, are resolved:

**Fail-closed interaction (formerly OQ-4)**: UNDECIDED-into-Triage is part of the fail-closed architecture, not a relaxation. Only a determinate ALLOW opens the gate. Everything else remains closed. Triage is part of the closed system, not an exception to it. Stated in Sections 3 and 4.

**Pre-check / intake layer (formerly OQ-9)**: Rejected as a separate architectural layer. Completeness and sufficiency checking is part of Pass. Stated in Section 4.

**Structural-growth-triggered disposition (formerly OQ-8)**: Resolved as DEFER_STRUCTURAL_DEFICIENCY (Section 6). In development and governance contexts, cases may be placed on hold pending research or structural review.

**Governance of structural feedback (formerly OQ-7)**: The Structural Feedback Function proposes and informs; it must not act. Structural modification is limited to changes reviewed and approved by the product owner and governance operator. Stated in Section 7 and enforced by INV-8.

**DEFER subtype formalization (formerly OQ-4 of fourth revision)**: Resolved. DEFER is split into DEFER_INPUT_INSUFFICIENCY and DEFER_STRUCTURAL_DEFICIENCY as separate typed outputs with distinct record requirements (Section 6).

**Triage classification determinism (formerly OQ-2)**: Resolved. Triage must exhaust deterministic classification wherever feasible before crossing into judgment. A deterministic Triage act may include identifying structural deficiency and emitting a structural signal. INV-9 requires that Triage identify, for each act, whether it was performed on deterministic or judgmental grounds. The commitment is: deterministic where feasible, judgment only where deterministic classification is insufficient.

**Doctrine scope (formerly OQ-3)**: Resolved. This is a general project doctrine using primitives intended to cross domains. Different domains may require different amounts of Triage and Structural Feedback activity, and that variation is useful evidence of where deterministic structure remains underbuilt. Domain-specific adaptation is expected and legitimate; the core architecture and invariants apply universally.

**Final doctrine name (formerly OQ-5)**: Resolved. "Residual Discretion Doctrine" — finalized 2026-03-08.

---

## 14. OPEN QUESTIONS

### OQ-1: Formal Triage exhaustion criteria

Can Triage exhaustion be verified mechanically, or must it remain audit-based? Candidate approaches are identified but none are adopted.

### OQ-2: Domain-specific Triage and Structural Feedback calibration

Different domains will require different amounts of Triage activity and Structural Feedback processing. What governs the calibration of these levels per domain? How is "underbuilt" distinguished from "appropriately minimal" for a given domain?

### OQ-3: Structural Feedback Function observation scope

What operational telemetry may the Structural Feedback Function observe? Structural signals from Triage are clearly in scope. "Broader operational patterns" and "approved operational data" require boundaries, especially in deployment contexts where privacy and scope constraints apply.

---

## 15. RECOMMENDATION

### Readiness assessment

This specification is structurally complete at the doctrine level. It defines the architecture (three levels with one-way flow), the sole-resolver constraint, the hybrid diagnostic layer with basis-identification requirements, the typed outputs with explicit admission conditions and exclusions, the governed structural feedback function, the invariants, the attestation semantics, the feedback loop, and the language discipline governing interpretation. It resolves prior blocking questions. It identifies remaining open questions explicitly and narrowly.

### What remains before canonization

No blocking open questions remain. The remaining open questions (OQ-1 formal exhaustion criteria, OQ-2 domain calibration, OQ-3 observation scope) are important for operational maturity but do not block canonization of the doctrine itself.

Canonization requires acceptance by the product owner.

### Status

[CANDIDATE] — structurally complete, no blocking open questions, pending acceptance by the product owner.
