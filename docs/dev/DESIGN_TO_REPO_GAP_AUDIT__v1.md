# Design-to-Repo Gap Audit v1

## Objective

Compare the canonical design corpus on main against actual current-main implementation to classify which design-backed capabilities are unimplemented, partially realized, stale, underdesigned, or previously misread as missing. Determine whether the project is now blocked more by missing implementation of already-designed work, by missing next-wave design, or by a mix of both.

## Why This Audit Was Needed

Recent repo-only tranche and formulation probes repeatedly collapsed into already-consumed work, not-distinct-enough candidates, or design-blocked families. The control plane reached `NEXT_WORKFRONT_FORMULATION` without resolving whether the real bottleneck is missing implementation of existing design or missing new design for the next wave. This audit provides the lens to answer that question directly.

## Base SHA

`1feb9ea32537f42d166f29df71adf4450cedc378` (current `main`)

## Design Corpus Surveyed

### Authoritative control-plane references
- `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
- `docs/dev/CANONICAL_STATUS_AND_BASELINE_ALIGNMENT__v1.md`
- `docs/dev/POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`
- `docs/dev/APPLICATIONS_INDEX.md`
- `docs/dev/WORK_QUEUE.md`

### Design artifacts audited against implementation
- RDD: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- Signing: `docs/dev/EPIC_SIGNING.md`, `docs/dev/ATTESTATION_SPEC.md`
- FS_DELETE: `docs/dev/EPIC_PHASE_2D.md`
- FS_PROMOTE: `docs/dev/EPIC_PROMOTION.md`
- Foundation v0: `docs/dev/FOUNDATION_V0_ADMISSIBILITY_GATE.md`
- AAT: `docs/dev/AAT_v0_GATE_B_CONTRACT.md`, `docs/dev/AAT_v0_GATE_C.md`, `docs/dev/AAT_v0_PROFILES.md`, `docs/dev/AAT_SHIM_PROOF_BUNDLE_CONVENTION.md`, `docs/dev/AAT_SHIM_OPERATOR_PILOT.md`, `docs/dev/HOT_SHIM_VALIDATE_PROOF_BUNDLE__AAT.md`
- Messaging: `docs/dev/MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`, `docs/dev/MESSAGING_CAPABILITY_REGISTRY_AND_MAPPING_SCHEMA__v1.md`, `docs/dev/MESSAGING_INVOCATION_SCHEMA__v1.md`, `docs/dev/MESSAGING_DECISION_RECORD_EXTENSION__v1.md`, `docs/dev/MESSAGING_REASON_CODES__v1.md`, `docs/dev/MESSAGING_CONFORMANCE_TEST_DESIGN__v1.md`, `docs/dev/MESSAGING_PROXY_LIFECYCLE__v1.md`
- GovMCP maturity: `docs/dev/BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md`, `docs/dev/BROADER_GOVMCP_TOOL_CATALOG_SEAM_MAP__v1.md`, `docs/dev/GOVMCP_INSPECTABILITY_QUERY_SEAM_POST_IMPLEMENTATION_REVIEW__v1.md`, `docs/dev/GOVMCP_TOOL_CATALOG_SEAM_POST_IMPLEMENTATION_REVIEW__v1.md`
- Proof/export: `docs/dev/CROSS_CUTTING_PROOF_EXPORT_EXTERNAL_DEFENSIBILITY_BUNDLE__v1.md`, `docs/dev/PROOF_PACKET_HANDOFF_CONTRACT_CONVERGENCE__v1.md`, `docs/dev/SHIPPED_BUNDLE_VALIDATOR_PARITY_AND_EXTERNAL_CONTRACT_CONVERGENCE__v1.md`
- Invariants: `docs/dev/INVARIANTS_MAP.md`
- Core: `docs/SCOPE.md`, `docs/POLICY.md`, `docs/THREAT-MODEL.md`
- Speculative: design-memos for Coding Agent Overlay, Model Delta Engine, Verified AI Taxonomy, Case Strength

---

## Gap Classification Map

### 1. DESIGNED_AND_STILL_INTENDED_BUT_UNIMPLEMENTED

#### 1A. FS_PROMOTE (Cross-Root Promotion Capability)
- **Design source**: `docs/dev/EPIC_PROMOTION.md`
- **Design completeness**: High. Full design with invariants (INV-PROMO-001 through 007), reason codes (RC-PROMO-*), required intent fields, guarded workflow (10 steps), required tests (T-PROMO-001 through 008), and audit expectations.
- **Implementation evidence**: Zero. `FS_PROMOTE` is not in `capabilities/capability-registry.json`. No implementation code exists. Grep for `FS_PROMOTE` returns only the design document.
- **Why this is a real gap**: The design is explicit, coherent, and still intended. Nothing in the control plane declares it consumed or superseded. The `FS_MOVE` cross-root deny invariant (INV-PROMO-001) remains active and the design was created specifically to provide a sanctioned alternative.
- **Urgency**: Medium. Not blocking core governance operations, but FS_PROMOTE is the only designed solution for a recurring cross-root movement need.

#### 1B. RDD Terminal Judgment Runtime
- **Design source**: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md` (explicitly deferred)
- **Design completeness**: Schema exists (v0.2 record schema defines Terminal Judgment record type). Chain verification rules for terminal records are partially landed. Runtime implementation is explicitly deferred from v1.
- **Implementation evidence**: No runtime Terminal Judgment evaluator exists. Terminal Judgment as schema type is present in chain verification rules.
- **Why this is a real gap**: The design explicitly names this as deferred, but it remains part of the intended RDD architecture. The gap between schema-level support and runtime absence is real.
- **Urgency**: Low. Explicitly deferred, and the current RDD v1 path is complete without it.

#### 1C. RDD Second UNDECIDED Case Class
- **Design source**: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md` ("High-value but deferred beyond v1")
- **Design completeness**: Low. The doctrine describes the concept of extending to a second case class, but no specific second case class is selected or designed.
- **Implementation evidence**: None. Only FS_COPY dest-exists case class is implemented.
- **Why this is a real gap**: Design intent is explicit (extend to more case classes), but specific design for a second one does not exist.
- **Urgency**: Low. This straddles the boundary between unimplemented design and underdesigned area.

---

### 2. DESIGNED_AND_PARTIALLY_REALIZED

#### 2A. GovMCP Broader Maturity
- **Design sources**: `BROADER_GOVMCP_MATURITY_SEAM_MAP__v1.md`, `BROADER_GOVMCP_TOOL_CATALOG_SEAM_MAP__v1.md`, tool-catalog/inspectability/query seam post-implementation reviews
- **What is implemented**: Minimum required path, inspectability/query seam, tool-catalog exposure coherence, tool-catalog slice/query seam — all landed baseline.
- **What remains**: Broader connector completion, broader tool-catalog maturity, broader MCP exposure-layer consistency, broader GovMCP ergonomics. These are characterized in the design corpus but not yet bounded into executable specification.
- **Classification rationale**: The bounded seams that were designed and scoped are implemented. What remains is the larger maturity envelope that the seam maps identify but do not fully specify.

#### 2B. Messaging Follow-On
- **Design sources**: 7 messaging design artifacts; `MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`
- **What is implemented**: First slice (TASK_399) and replay-strengthening second slice (TASK_400). `MSG_SEND` and `MSG_REPLY` in capability registry. `scripts/messaging_surface.py`. Forwarding receipts. 16 `RC-MSG-*` reason codes wired. Content blindness, canonical destination authority, ALLOW/DENY-only.
- **What remains**: Messaging follow-on beyond first two slices. No global rate-metering (only bounded structural rate metadata in slice 1). No triage/UNDECIDED for messaging. Design explicitly excludes shell execution governance, web request governance, generic proxy infrastructure, DLP, content moderation.
- **Classification rationale**: The proof surface is architecturally closed for its bounded first two slices. The design explicitly scopes future expansion as separate follow-on work.

#### 2C. AAT / Foundation v0 Admissibility
- **Design sources**: `FOUNDATION_V0_ADMISSIBILITY_GATE.md`, `AAT_v0_GATE_B_CONTRACT.md`, `AAT_v0_GATE_C.md`, `AAT_v0_PROFILES.md`, shim docs
- **What is implemented**: Core AAT validators (kernel, mechanical, consistency, property), Gate A, Gate B ledger append, Gate C wrapper, `CORE_GENERIC` and `TOOL_EXEC` profiles, Foundation v0 admissibility gate, shim integration with validate-proof-bundle, AAT stage-into-proof-bundle helper. Extensive golden-pass and golden-fail test fixtures.
- **What remains**: Control plane identifies "AAT / Foundation v0 admissibility convergence restock candidate" as live-but-unbounded. Broader operator hardening and convergence between AAT surfaces and the rest of the governance pipeline.
- **Classification rationale**: Core AAT is materially implemented. What remains is integration convergence and broader operator-facing maturity, which is not yet bounded into a clear next specification.

#### 2D. Proof/Export/External Defensibility
- **Design sources**: `CROSS_CUTTING_PROOF_EXPORT_EXTERNAL_DEFENSIBILITY_BUNDLE__v1.md`, attestation spec sections
- **What is implemented**: Proof-packet build/verify, attestation bundle pack/verify, receipt/tool-event/tool-catalog export commands, external proof-bundle validator, release-gate suite, external packaging checks, shipped-bundle validator parity. Extensive test coverage.
- **What remains**: Broader export contract convergence, broader external-defensibility hardening residue. The cross-cutting bundle document identifies three fronts (export contract convergence, proof-packet/verifier hardening, external validator/parity hardening) that are partially addressed but not fully closed.
- **Classification rationale**: Core handoff seams are landed. Broader hardening and convergence remain as live-but-unbounded residue.

#### 2E. RDD v1 Explicit Deferrals
- **Design source**: `RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- **What is implemented**: Phases 1-11 complete. Pass UNDECIDED emission, Triage evaluator, chain verification extension, structural feedback plumbing, replay extension, external triage criteria, selector routing, selector contract strictness, selector-mode explicit wiring, source contract hardening, request-source strictness.
- **What remains as explicit deferrals**:
  - Structural Feedback Function analysis, pattern detection, proposal generation
  - Multi-domain support
  - Multi-case-class triage
  - Formal triage exhaustion verification
  - Domain calibration framework
  - Structural Feedback observation scope governance
  - Feedback evaluation machinery
  - Triage MCP server inline integration
- **Classification rationale**: v1 is complete per its own boundaries. The deferrals are real design-backed capabilities that remain outside the v1 fence. They are partially realized because the foundational infrastructure (signal extraction, chain linking, schema) exists.

#### 2F. Standalone CLI Formalization
- **Design source**: `docs/dev/APPLICATIONS_INDEX.md` ([NEEDS_VALIDATION])
- **What is implemented**: `scripts/policy-eval.py` functions as a CLI. Accepts request JSON, outputs PolicyRecord, exit codes for ALLOW/DENY.
- **What remains**: Argument parsing (--help, --version), chain management, explicit CLI packaging.
- **Classification rationale**: Functional but not formalized as a standalone product surface.

---

### 3. DESIGNED_BUT_SUPERSEDED_OR_STALE

#### 3A. "Generic GovMCP Maturity" as Next Lane
- **Evidence**: `CANONICAL_STATUS_AND_BASELINE_ALIGNMENT__v1.md` explicitly declares "the older 'broader GovMCP maturity' selector frame is stale" and `CURRENT_MAIN_CAPABILITY_MAP.md` warns "do not collapse consumed GovMCP seam closures and still-live governance-evidence formulation work into one generic 'GovMCP maturity' family."
- **Classification rationale**: The framing is explicitly superseded by canon repair. Individual GovMCP seams remain valid, but the blunt "GovMCP maturity" label is stale.

#### 3B. Generic "Deployment" and "Observability" as Selection-Ready Families
- **Evidence**: Control plane explicitly warns against treating "broad deployment, observability, and proof/export labels as too blunt unless they are restocked into bounded current-main-useful workfronts."
- **Classification rationale**: These were once live family labels but have been consumed or shown to be too blunt for direct selection.

#### 3C. Case Strength as Governance-Layer Extension
- **Evidence**: `docs/dev/design-memos/2026-02-24__case-strength-system__eval.md` recommends "Do not pursue as governance-layer extension" and "If Case Strength is valuable, pursue as separate application with separate repo."
- **Classification rationale**: Explicitly recommended against as governance-layer scope. Concept remains valid as a separate application idea.

#### 3D. Model Delta Engine as Canonical Lens
- **Evidence**: Evaluation memo marks it [SPECULATIVE] and recommends "Adopt framing as [SPECULATIVE] perspective, not as canonical lens."
- **Classification rationale**: Conceptual framing that was evaluated and explicitly not adopted as canonical. Does not represent a real implementation gap.

#### 3E. Distributed Replay Network / HTTP API Wrapper
- **Evidence**: Both listed as [SPECULATIVE] in `APPLICATIONS_INDEX.md` with "no design or implementation."
- **Classification rationale**: Speculative concepts with no design depth. Not real gaps.

---

### 4. UNDERDESIGNED_AREA_NEEDING_NEW_DESIGN

#### 4A. Post-Traceability Governance Evidence Product Work
- **Evidence**: This is the strongest current formulation candidate identified by the control plane. The capability map names "evidence-path coherence" as the strongest currently-derived formulation winner, with "record-to-packet governance evidence coherence" as the latest narrower follow-on formulation need.
- **What exists**: The receipt/tool-event traceability tranche is consumed baseline. Coverage stamps are implemented. Proof-packet and attestation bundles are landed. But no bounded design specification exists for what "governance evidence coherence" means as a product surface or what it should guarantee beyond what is already on main.
- **Why this is underdesigned**: The formulation candidate exists as a direction, not as a specification. There is no design document defining what "evidence-path coherence" concretely requires, what contracts it enforces, what tests prove it, or what boundary separates it from already-consumed traceability work.
- **This is the most important underdesigned area in the repo.**

#### 4B. Policy Evolution and Versioning
- **Evidence**: `APPLICATIONS_INDEX.md` lists "Policy Evolution & Versioning" under "Open Questions / Needs Placement" with "Not addressed in Phase 2/3 design."
- **What exists**: No design. Questions about versioning policy rules over time, re-evaluating old decisions under new policies, and handling breaking changes in capability registry are listed but unanswered.
- **Classification rationale**: Genuinely underdesigned. Not yet important enough to be a near-term blocker, but real as a conceptual gap.

#### 4C. Multi-Actor Scenarios
- **Evidence**: `APPLICATIONS_INDEX.md` lists under "Open Questions / Needs Placement" with "Not addressed in Phase 2/3 design."
- **Classification rationale**: Underdesigned. Concurrent requests from different actors, actor-specific allowlists, and actor-level access control are all undesigned.

#### 4D. Logging Completeness / Break-Glass / UNGOVERNED Propagation
- **Evidence**: Verified AI Taxonomy eval identifies gaps to O3/E2 including persistent sequence numbers, LOGGING_FAILURE handling, break-glass detection, UNGOVERNED marker propagation.
- **What exists**: The taxonomy is [SPECULATIVE] and these gaps are identified but not designed.
- **Classification rationale**: These are real conceptual areas where the system has no design, but they arise from a speculative assessment framework and may not represent intended next-wave priorities.

---

### 5. ALREADY_IMPLEMENTED_BUT_PREVIOUSLY_MISREAD

#### 5A. Time Ribbon Rendering
- **Evidence**: `APPLICATIONS_INDEX.md` lists this as `[DESIGN_ONLY]` with "Design sketched, no implementation." However: `scripts/attest/time_ribbon.py` exists as implementation, `tests/test_integrated_negative_bad_time_ribbon.sh` exists as a test, `docs/dev/evidence/TASK_098/` contains evidence, and the Integrated E2E Determinism Tests section in `APPLICATIONS_INDEX.md` itself lists TASK_098 (Time ribbon render script) as `[IMPLEMENTED]`.
- **Classification rationale**: The `[DESIGN_ONLY]` label under "Downstream Applications" is contradicted by the `[IMPLEMENTED]` label under "Integrated E2E Determinism Tests" and by the actual code and evidence on main. The time ribbon render script is implemented; the stale label is a documentation inconsistency.

#### 5B. Coverage Stamp / Phase 2D Implementation
- **Evidence**: `EPIC_PHASE_2D.md` describes Phase 2D as "scoping/contracts/tests planning only" with "No implementation changes are in scope for this tranche." However, `scripts/coverage_stamp.py` exists, and there are multiple coverage stamp tests: `test_coverage_stamp_replay.sh`, `test_coverage_stamp_verify_chain.sh`, `test_coverage_stamp_cross_tool_parity.sh`, `test_coverage_stamp_ordering_determinism.sh`, `test_coverage_stamp_policy_eval.sh`, `test_proof_packet_coverage_stamp_contract.sh`.
- **Classification rationale**: Phase 2D scoping may have been followed by implementation in later task bundles. The coverage stamp is materially implemented on main despite the EPIC framing it as scoping-only.

#### 5C. Coding Agent Overlay
- **Evidence**: Evaluation memo marks it `[IMPLEMENTED]` operationally via RUNBOOK.md, OPS_CANONICAL.md, AGENT_CONTRACT.md, and helper scripts. Not a code gap.
- **Classification rationale**: This was evaluated, adopted, and is operational. Not a gap.

---

### 6. TOO_AMBIGUOUS_TO_TREAT_AS_REAL_GAP

#### 6A. Performance Benchmarks
- **Evidence**: Listed in `APPLICATIONS_INDEX.md` open questions. No design, no clear intent.
- **Classification rationale**: Mentioned as a question, not as intended design. No evidence this is planned.

#### 6B. Cross-Language Implementations
- **Evidence**: Listed in `APPLICATIONS_INDEX.md` open questions. Python is reference implementation.
- **Classification rationale**: Mentioned as a question, not as intended design. No evidence of plans for Rust/Go/TypeScript ports.

#### 6C. Verified AI Taxonomy as Implementation Target
- **Evidence**: Evaluation memo marks it [SPECULATIVE] and recommends Phase 1 assessment only.
- **Classification rationale**: The taxonomy is an assessment lens, not a gap in the governance-layer itself. If adopted, it would create new design requirements (O3, P2 gaps), but adoption itself is not confirmed.

---

## Summary Classification Table

| # | Area | Classification | Design Strength | Implementation State | Priority Signal |
|---|------|---------------|-----------------|---------------------|----------------|
| 1A | FS_PROMOTE | UNIMPLEMENTED | High | None | Medium |
| 1B | RDD Terminal Judgment Runtime | UNIMPLEMENTED | Medium (schema only) | Schema-level only | Low (deferred) |
| 1C | RDD Second Case Class | UNIMPLEMENTED | Low | None | Low (deferred) |
| 2A | GovMCP Broader Maturity | PARTIAL | Medium (seam maps) | Core seams landed | Medium |
| 2B | Messaging Follow-On | PARTIAL | High (7 design docs) | First 2 slices landed | Medium |
| 2C | AAT/Fv0 Convergence | PARTIAL | High | Core implemented | Medium |
| 2D | Proof/Export Hardening | PARTIAL | High | Core seams landed | Medium |
| 2E | RDD v1 Deferrals | PARTIAL | Medium (enumerated) | v1 infrastructure done | Low |
| 2F | CLI Formalization | PARTIAL | Low | Functional | Low |
| 3A | Generic GovMCP Maturity | SUPERSEDED | — | — | — |
| 3B | Generic Deployment/Observability | SUPERSEDED | — | — | — |
| 3C | Case Strength Extension | SUPERSEDED | — | — | — |
| 3D | Model Delta Engine Lens | SUPERSEDED | — | — | — |
| 3E | Distributed Replay / HTTP API | SUPERSEDED | — | — | — |
| 4A | Governance Evidence Coherence | UNDERDESIGNED | Direction only | Baseline consumed | **Highest** |
| 4B | Policy Evolution/Versioning | UNDERDESIGNED | None | None | Low |
| 4C | Multi-Actor Scenarios | UNDERDESIGNED | None | None | Low |
| 4D | Logging/Break-Glass/UNGOVERNED | UNDERDESIGNED | Speculative only | None | Low |
| 5A | Time Ribbon Rendering | MISREAD | Implemented | Implemented | — |
| 5B | Coverage Stamp (Phase 2D) | MISREAD | Implemented | Implemented | — |
| 5C | Coding Agent Overlay | MISREAD | Implemented | Implemented | — |
| 6A-C | Perf/Cross-Lang/Verified AI | AMBIGUOUS | None/Speculative | None | — |

---

## Final Judgment: Implementation-Blocked, Design-Blocked, or Mixed?

**MIXED, tilting toward DESIGN-BLOCKED.**

### Why not purely implementation-blocked
The most important designed-but-unimplemented item (FS_PROMOTE) is a standalone capability addition, not the project's strategic bottleneck. The RDD deferrals are intentional and lower-priority. The partially-realized areas (broader GovMCP, messaging follow-on, AAT convergence, proof/export hardening) all need restocking or bounded specification before they could become implementation tranches — making them partially design-blocked.

### Why not purely design-blocked
Some designed-but-unimplemented work does exist (FS_PROMOTE, RDD Terminal Judgment). Some partially-realized areas have enough existing design that bounded implementation scoping could proceed without major new design effort. The foundational infrastructure for most next-wave work is already on main.

### Why mixed tilting design-blocked
The control plane already reached `NEXT_WORKFRONT_FORMULATION` because repeated attempts to find a clearly bounded, clearly unconsumed implementation tranche failed. The strongest next-wave candidate ("post-traceability governance evidence product work" → "evidence-path coherence" → "record-to-packet governance evidence coherence") exists only as a formulation direction, not as a bounded specification. Without new design work to define what this means concretely, no implementation tranche can be dispatched for the project's most important next move.

---

## Most Important Remaining Design-Backed or Design-Needed Work Areas

Ranked by strategic importance:

1. **Record-to-packet governance evidence coherence** — the current formulation winner. Needs bounded design specification before it can become implementation work.
2. **FS_PROMOTE** — full design exists, could become an implementation tranche without new design.
3. **GovMCP broader maturity restocking** — needs bounded seam selection beyond the already-landed seams.
4. **AAT / Foundation v0 convergence restocking** — needs bounded convergence spec.
5. **Messaging follow-on beyond first two slices** — needs scoping for what slice 3+ looks like.
6. **Proof/export broader hardening** — needs bounded specification for remaining external-defensibility residue.
7. **RDD continuation beyond v1** — lower priority, requires product decision on second case class.

---

## Recommended Next Design-Mode Priority

**Bounded design specification for "record-to-packet governance evidence coherence."**

### Why
- It is the strongest current-main-derived formulation winner.
- It addresses the actual bottleneck: the project cannot dispatch an implementation tranche for its most important next move because no bounded design exists for it.
- It builds on consumed traceability baseline without replaying it.
- It stays inside the governance evidence product lane rather than reopening consumed GovMCP or observability families.
- Completing this design would directly unblock the transition from `NEXT_WORKFRONT_FORMULATION` to a bounded execution tranche.

### What the design should define
- What "evidence coherence" concretely means as a verifiable property of the record-to-packet path
- Which existing surfaces and contracts are in scope (record emission → proof-packet → external validation)
- What invariants or consistency guarantees are missing from the current baseline
- What tests would prove coherence beyond what current tests already prove
- Clear boundary between this work and already-consumed traceability or inspectability closures

### Alternative if FS_PROMOTE is higher priority
If the product owner determines that FS_PROMOTE is more urgently needed than governance evidence coherence, FS_PROMOTE could become the next implementation tranche immediately — its design is already complete. This would bypass the design-blocked bottleneck by selecting a different work area that is implementation-ready.

---

## Evidence That Would Overturn the Recommendation

1. **FS_PROMOTE is the true bottleneck**: If the product owner confirms that cross-root promotion is more urgently needed than evidence coherence, FS_PROMOTE should be dispatched as implementation rather than pursuing new design work.
2. **A sharply bounded GovMCP seam is found**: If repo-grounded evidence reveals a clearly bounded, clearly unconsumed GovMCP maturity seam that can be specified and dispatched without major new design, it could bypass the evidence-coherence formulation.
3. **Evidence coherence is already sufficient**: If analysis shows that the current record-to-packet path is already coherent enough and the "gap" is illusory, then the project needs a different formulation candidate entirely.
4. **External demand shifts priority**: If compliance, deployment, or external consumer needs prioritize AAT convergence, proof/export hardening, or messaging follow-on above evidence coherence.
5. **A new design candidate emerges**: If a clearly higher-leverage, clearly bounded design direction is identified that was not visible in the current design corpus.

---

## Documentation Inconsistencies Found

1. **Time Ribbon Rendering**: `APPLICATIONS_INDEX.md` labels it `[DESIGN_ONLY]` under "Downstream Applications" but `[IMPLEMENTED]` under "Integrated E2E Determinism Tests." The implementation exists. The downstream-application label is stale.
2. **Phase 2D / Coverage Stamp**: `EPIC_PHASE_2D.md` describes the tranche as "scoping/contracts/tests planning only" but coverage stamps are materially implemented on main.
3. **APPLICATIONS_INDEX baseline SHA**: The document does not include a baseline SHA or freshness marker, making it harder to detect staleness.
