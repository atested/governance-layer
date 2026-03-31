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
