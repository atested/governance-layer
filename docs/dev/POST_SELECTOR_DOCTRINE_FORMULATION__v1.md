# Post-Selector Doctrine Continuation Formulation v1

## Objective
Isolate a bounded post-selector Residual Discretion Doctrine workfront that is still unconsumed on current main and articulate its design so a later tranche selection can claim it without replaying selector-mode work.

## Post-Selector Baseline
- `docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md` flags RDD continuation as live but unbounded after the selector-mode tranche.
- The selector-mode tranche itself is materially consumed (`docs/dev/RDD_SELECTOR_MODE_TRANCHE_POST_IMPLEMENTATION_REVIEW__v1.md` and the queue entries `TASK_311`–`TASK_314` are satisfied).
- Current canonical truth (`docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`, `docs/dev/POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`) no longer treats RDD as the immediate next workfront, so any post-selector continuation must be deliberately formulated.
- Existing RDD plan (`docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`) already enumerates the triage evaluator, chain verification, replay, and criteria selector phases, giving real candidate surfaces.

## Candidate Workfront Shapes

### Candidate A — Case-Class Continuation (e.g., triage evaluator for FS_COPY dest-exists)
- Surface: build on `TASK_320`–`TASK_322` direction that formalizes the triage evaluator for the newly emitted UNDECIDED case class.
- Operator value: ensures the doctrine can admit/deny more case classes deterministically before they reach Gate C.
- Distinctness test:
  1. Selector-mode work only emitted Gate C decisions; this candidate adds new case-class handling semantics beyond Gate C outputs. → **DISTINCT** (triage evaluator expansion is a new doctrinal seam).
  2. Only overlaps validator/profile expansion if it leaks into per-profile telemetry; a bounded candidate keeps focus on the specific case class definitions. → remains **DISTINCT**.
  3. Not broad doctrine redesign because it stays within the triage evaluator contract defined in the plan.
- Boundability: definable by selecting one UNDECIDED or TERMINAL case class to cover, plus its acceptance tests.

### Candidate B — Chain Verification/Terminal Judgment
- Surface: extend `TASK_323`/`TASK_324` chain verifier coverage to include triage/terminal records and ensure multi-record doctrinal traces remain coherent.
- Operator value: gives deterministic proof that chains containing triage/terminal signals remain admissible, supporting higher-order decisions.
- Distinctness test:
  1. Selector-mode work did not verify multi-record chains that include new triage outputs; this candidate adds verification logic beyond the consumed path. → **DISTINCT**.
  2. Does not revert into validator/profile expansion because it remains a general doctrinal integrity check rather than actor-specific metrics. → stays **DISTINCT**.
  3. Not a repackaged replay or proof/export surface; the focus stays on doctrinal chain coherence.
- Boundability: target a fixed set of triage/terminal record combinations and their deterministic verification rules.

### Candidate C — Multi-Case-Class Triage Orchestration
- Surface: design an orchestrated triage/breach flow that covers multiple UNDECIDED signals, akin to `TASK_329`–`TASK_332` selector routing.
- Operator value: makes the doctrine ready for production by describing how selectors route across case classes.
- Distinctness test:
  1. Selector-mode triaged a single path; orchestrating multiple case classes is a new expansion, but the plan currently already lists this as later-phase work. → **DISTINCT** if the formulation bounds the first additional class.
  2. Could collide with validator/profile expansion if it starts specifying actor-level toggles; keep the formulation at the case-class routing level. → remains **DISTINCT** when scoped.
  3. Not a general Doctrine redesign; it's the natural next step after selector-mode.
- Boundability: pick the next immediate case-class selector pair and define its therapeutic criteria.

## Comparative Assessment
- Distinctness: All three candidates pass the fail-closed check because they extend beyond the consumed selector-mode seam; Candidate A is the most concretely scoped, Candidate B is highest-value for assertion, and Candidate C is more productizing but still bounded if it only adds one extra class.
- Strategic value: Candidate B beats the others if doctrine integrity is the priority; Candidate A matters for new capability, Candidate C for operator-facing triage clarity.
- Future boundability: Candidate A and B can each be defined over one deterministic case class or chain combination for a single tranche. Candidate C risks becoming too broad if it tries to cover the entire selector routing system.

## Recommendation
**Candidate B (Chain Verification/Terminal Judgment)** is the immediate formulation winner: articulate the next doctrinal chain-verification tranche that proves triage/terminal records coexist with the existing selector chain.  
**Backup candidate:** Candidate A (Case-Class Continuation) because it offers a clearly bounded addition of one new case class to the triage evaluator.

### Exact Next Control Step
Formulate the bounded Chain Verification extension: specify the new triage/terminal record types to verify, the required deterministic checks, the acceptance tests, and the operator evidence that proves the chain remains coherent. This produces the claim-ready artifact for the next tranche-selection pass.

## Evidence That Would Overturn This
- Discovery that the chain-verification surface is already consumed on main or replicates existing selectors (i.e., no new triage records remain unverified).  
- A canonical artifact showing Candidate A's next case class is already implemented.  
- Operator guidance prioritizing multi-case-class orchestration (Candidate C) instead of chain verification.
