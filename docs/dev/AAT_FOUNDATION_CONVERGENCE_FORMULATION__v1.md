# AAT/Foundation v0 Admissibility Convergence Formulation v1

## Objective
Determine whether there is a bounded AAT/Foundation v0 admissibility convergence workfront beyond the consumed stage→shim→Gate C operator path, and if so package the missing design for later tranche selection.

## Baseline Summary
- The operator-path tranche that stages requests, runs the shim, and exercises Gate C is treated as already consumed on current main by later planning surfaces, but no current-main `TASK_401` artifact path exists.
- The repaired canon now highlights formulation mode and treats AAT convergence as the top design-blocked candidate (`docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`, `docs/dev/POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`).
- Convergence is meant to span AAT tooling plus emerging Foundation v0 admissibility semantics (scripts/tools in `AAT`/`foundation` directories), but no bounded convergence definition exists yet.

## Candidate Workfront Shapes

### Candidate A — Foundation Policy Registry Tie-In
- **Claim**: Define a bounded workfront that ties the AAT Gate C decision outputs to Foundation v0 policy registry entries so convergence enforces the same admissibility constraints across both surfaces.
- **Distinctness tests**:
  - Consumed operator path already emits Gate C outcomes; the new workfront must instead define how those outcomes map to Foundation v0 policy entries. Without that mapping, it is indistinct from Gate C work. → **DISTINCT** if mapping surfaces (e.g., `foundation/policies.yaml`, `aat/policy_registry.py`) exist; otherwise **NOT DISTINCT ENOUGH**.
  - Not validator/profile expansion unless it documents how Registry constraints trigger Gate C decisions; not a broad redesign, only a bounded mapping definition. → remains **DISTINCT** if scoped narrowly.
  - Not generic proof/export or deployment, as it stays within governance policy alignment.

### Candidate B — Admissibility Evidence Exchange Contract
- **Claim**: Formulate a bounded contract for how admissibility evidence (e.g., operator intents, policy citations) is exchanged between AAT shim and Foundation v0 consumers, stabilizing acceptance criteria for convergence.
- **Distinctness tests**:
  - Operator-path baseline already moves intents through Gate C; this candidate must define new evidence artifacts or canonical fields beyond Gate C (e.g., new `AAT` metadata files or `foundation/evidence_exchange.md`). Without them, it duplicates consumed work → **NOT DISTINCT ENOUGH**.
  - Validator/profile expansion is avoided only if the evidence contract stays governance-focused (no validator/actor-specific metrics). → **NOT DISTINCT ENOUGH** until evidence artifacts are proposed.
  - Not proof/export or deployment, since the focus stays on governance evidence packaging.

### Candidate C — Operator-Facing Convergence Runbook
- **Claim**: Craft a bounded operator-facing runbook specifying how to interpret Gate C outcomes, Foundation admissibility rules, and convergence escalation paths, turning the convergence concept into a concrete control-plane artifact.
- **Distinctness tests**:
  - Differs from consumed code by being a documentation/design artifact rather than implementation; convergence claim holds if it ties Gate C outputs to Foundation v0 policies in the runbook (`docs/dev/runbook/convergence.md`). → **DISTINCT** only if the runbook defines decision points and acceptance proofs not currently documented.
  - Not validator/profile expansion since it is for operators; not a broad redesign unless it invents new control surfaces. → remains **DISTINCT** with careful scope.
  - Not proof/export/deployment as long as it stays focused on operator-facing convergence operations.

## Comparative Assessment
- Candidate A and C can be distinct if new artifacts (e.g., mapping files, runbook sections) are defined; B currently lacks concrete artifacts and therefore fails the distinctness test.
- Strategic value is highest for Candidate A if it produces deterministic convergence semantics; Candidate C is helpful for operators but less precise.
- Future boundability depends on defining the exact surfaces (policy registry ties or runbook entries); without those deliverables, the lane stays diffuse.

## Recommendation
**Candidate A (Foundation Policy Registry Tie-In)** is recommended if a concrete mapping surface (file + acceptance proof) can be defined to tie Gate C outputs to Foundation v0 admissibility rules.

### Minimum Next Control Step
Formulate the mapping surface: produce a small spec detailing the policy registry entries, the Gate C outcome values they correspond to, the acceptance proofs/tests, and the operator visibility expectations. Once that form is built, re-run tranche selection to confirm implementation readiness.

## Evidence That Would Overturn This Conclusion
- Canonical repo evidence showing no new mapping surface exists or can be scoped without touching consumed artifacts (e.g., mapping already implicitly present in `foundation/policies.yaml`).  
- A clearer high-leverage driver for Candidate C or another lane discovered through fresh canonical analysis.  
- A subsequent merge that directly consumes the candidate candidate, leaving no gap to fill.
