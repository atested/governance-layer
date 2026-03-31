# Current-Main Governance Broad-State Delta Refresh After T408 v1

Base SHA: `54e4cf9fa849879e7ddfd474cfe86fbac7c128a5`
Prior broad-state baseline: `GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T405__v1.md` at `71ebff41`
Date: 2026-03-17

---

## 1) What Materially Changed On Main Because Of T405, T406, T407, and T408 Together

This refresh covers the four merges since the design-to-repo gap audit base (`1feb9ea3`):

### T405 (M139): Category 6 + Terminal Judgment
- **Category 6 case class** (`genuine_residual`): `policy-eval.py` emits `UNDECIDED` for FS_COPY with `requires_authorization: true` when no policy violations exist.
- **Terminal judgment runtime**: `scripts/terminal-judgment-eval.py` — standalone emitter with 8 validation rules, Ed25519 signing, chain append, `policy_decision` bridge.
- **Disposition taxonomy**: ALLOW, DENY, NON_RESOLUTION with four methods (`human_authority`, `bounded_estimation`, `random_tiebreak`, `non_resolution`).
- **RDD-to-Gate-C bridge**: `policy_decision` on terminal judgment mirrors `outcome`; Gate C consumes it without modification.
- **3-record chain verification**: Full pass(UNDECIDED) → triage(ESCALATION_JUSTIFIED) → terminal(ALLOW) chain verified. 13-case test suite.

### T406 (M140): Replay Outcome Governance Evidence
- **`governance_evidence.replay_outcome`** added to `proof_packet_verify_summary_v1`: pass/fail/unavailable semantics extracted from enclosed `replay_audit_report.json`.
- **`governance_evidence` propagated into `validate_proof_bundle_summary_v1`**: bundle validator summary now carries the same governance evidence block as proof-packet verify.
- **Three-state replay outcome tests**: pass, fail, unavailable cases all covered.
- This is the narrow replay-outcome tranche recommended by `RECORD_TO_PACKET_NEXT_TRANCHE_CONFIRMATION__v1.md`.

### T407 (M141): FS_PROMOTE Policy Evaluation
- **FS_PROMOTE in capability registry**: new governed tool entry with `FS_PROMOTE` capability class.
- **Policy evaluation for FS_PROMOTE**: `policy-eval.py` handles cross-root promotion with full intent validation, root-pair allowlist checking, source hash verification, artifact class checking, overwrite policy, path-under-root enforcement, and source type verification.
- **10 RC-PROMO-* reason codes**: ROOT-PAIR-DISALLOWED, SRC-MISSING, SRC-TYPE-DISALLOWED, HASH-MISMATCH-SRC, HASH-MISMATCH-DST, ARTIFACT-CLASS-DISALLOWED, OVERWRITE-DISALLOWED, PATH-DISALLOWED, plus existing RC-FS-CROSS-ROOT-DISALLOWED and RC-FS-HIDDEN-PATH reuse.
- **10-case policy test suite** (T-PROMO-001 through T-PROMO-010): cross-root FS_MOVE denial, root pair denial, hash mismatch, hidden path, valid promotion, record integrity, artifact class, overwrite, path disallowed, directory source.

### T408 (M141+1): FS_PROMOTE Bounded Execution
- **`scripts/fs-promote-exec.py`**: execution engine implementing EPIC_PROMOTION.md guarded workflow steps 8–10 (bounded copy+verify, completion record emission, chain re-verification).
- **Destination hash verification (INV-PROMO-004)**: post-copy hash comparison with fail-closed on mismatch.
- **Completion record emission (INV-PROMO-005)**: `promotion_completion` record type with `decision_record_hash`, `dst_hash_verified`, `src_content_hash_sha256`, `dst_content_hash_sha256`, `promotion_id`, and chain linkage.
- **5 execution-layer test cases** (T-PROMO-011 through T-PROMO-015): successful execution, completion-to-decision chain linkage, DENY record rejection, tampered record rejection, destination hash mismatch fail-closed.
- **Full test suite**: 74 assertions pass across 15 test cases.

---

## 2) Which Previously Live Directions Are Now Consumed Or Partially Consumed

### Newly consumed or partially consumed since the prior broad-state view

| Direction | Prior classification (post-T405) | Current classification | What changed |
|---|---|---|---|
| FS_PROMOTE | LIVE AND BOUNDED (implementation-ready) | **CONSUMED** | T407+T408 implemented the full EPIC_PROMOTION.md design: registry entry, policy evaluation (steps 1–7), execution engine (steps 8–10), all 7 invariants verified, all 8 required tests covered plus 7 additional execution-layer tests |
| Record-to-packet governance evidence coherence | LIVE AND BOUNDED (implementation-ready) | **PARTIALLY CONSUMED** | T406 landed the narrow replay-outcome tranche: `governance_evidence.replay_outcome` in proof-packet verify summary and propagation to bundle validator summary. The broader design spec's coverage-stamp cross-check and field-shape normalization remain open |
| Post-selector doctrine continuation | PARTIALLY CONSUMED | PARTIALLY CONSUMED (unchanged) | T405 was the last RDD-lane landing; T406–T408 did not touch RDD surfaces |

### Confirmed unchanged since prior broad-state view

| Direction | Classification | Status |
|---|---|---|
| AAT / Foundation v0 admissibility convergence | LIVE BUT NOT YET BOUNDED | No changes; still needs formulation |
| Messaging follow-on | LIVE BUT NOT YET BOUNDED | No changes; no third slice designed |
| Proof/export external-defensibility residue | PARTIALLY CONSUMED | T406 consumed additional residue; remaining is subsumed by broader hardening |
| Deployment / operationalization residue | CONSUMED | No changes |
| Combo A structured summary emission | LIVE BUT NOT YET BOUNDED | Unblocked by T405 but not advanced by T406–T408 |

---

## 3) Reassessment Of Major Directions

### A. Record-to-Packet Governance Evidence Coherence
- **Prior status**: LIVE AND BOUNDED (implementation-ready) — recommended next strategic direction
- **Post-T408 status**: **PARTIALLY CONSUMED**
- **What T406 shipped**: `governance_evidence.replay_outcome` (pass/fail/unavailable) added to `proof_packet_verify_summary_v1`; `governance_evidence` block propagated into `validate_proof_bundle_summary_v1`; three test cases covering pass/fail/unavailable.
- **What remains open from the design spec**:
  - Coverage-stamp cross-check between manifest and replay (`coverage_stamp_cross_check` field) — not landed
  - Field-shape normalization of `packet_hash` between the two summary surfaces — not landed
  - `replay_record_counts` and `replay_report_version` sub-fields — not landed (T406 landed `replay_outcome` only, not the full `governance_evidence` schema from the design spec)
- **Assessment**: The highest-value item in this lane (making governance replay verdict visible at summary level without raw artifact parsing) is now shipped. What remains is incremental coherence hardening: coverage-stamp cross-check is genuinely useful but narrow, field-shape normalization is a breaking change, and record-count sub-fields are supplementary detail. None of the residue represents a strategic step-change. This lane has moved from "strongest implementation-ready candidate" to "consumed core with incremental residue."

### B. FS_PROMOTE
- **Prior status**: LIVE AND BOUNDED (implementation-ready) — runner-up to record-to-packet
- **Post-T408 status**: **CONSUMED**
- **What T407+T408 shipped**: Full EPIC_PROMOTION.md implementation across two tranches:
  - T407: capability registry entry, policy evaluation (guarded workflow steps 1–7), 10 reason codes, 10 test cases
  - T408: execution engine (steps 8–10), destination hash verification (INV-PROMO-004), completion record emission (INV-PROMO-005), fail-closed execution, 5 execution test cases
- **What remains**: Nothing from EPIC_PROMOTION.md. All 7 invariants (INV-PROMO-001 through 007) are verified by test. All 8 originally required tests plus 7 additional execution-layer tests pass. The capability is fully landed.
- **Assessment**: This direction is closed. No further FS_PROMOTE work is needed unless product requests extensions (e.g., recursive directory promotion, additional root pairs, or new artifact classes).

### C. Post-Selector Doctrine Continuation
- **Prior status**: PARTIALLY CONSUMED
- **Post-T408 status**: PARTIALLY CONSUMED (unchanged)
- **What T406–T408 changed**: Nothing. These tranches were in the record-to-packet and FS_PROMOTE lanes, not RDD.
- **What remains**:
  - Combo A structured summary emission (verify-chain.py → structured JSON) — unblocked by T405, unbounded
  - Multi-case triage orchestration — explicitly deferred in RDD v1
  - Structural Feedback Function — explicitly deferred
  - Formal triage exhaustion verification — explicitly deferred
  - Second tool domain beyond FS_COPY — explicitly deferred
- **Assessment**: The highest-leverage post-selector work (terminal judgment, Category 6 case class) shipped in T405. The only non-deferred item is Combo A structured summary emission, which is a real follow-on but needs a bounded design spec. This lane is no longer a strategic priority.

### D. AAT / Foundation v0 Admissibility Convergence
- **Prior status**: LIVE BUT NOT YET BOUNDED
- **Post-T408 status**: LIVE BUT NOT YET BOUNDED (unchanged)
- **What T406–T408 changed**: Nothing.
- **Assessment**: Still needs formulation. The design backlog's blocking question remains unanswered: "What bounded operator-facing story defines the convergence workfront?" Core AAT (validators, gates, profiles, shim) is implemented. What's missing is the convergence spec that defines how AAT surfaces and Foundation v0 admissibility compose into a coherent operator-facing story. This is formulation work, not implementation work.

### E. Messaging Follow-On
- **Prior status**: LIVE BUT NOT YET BOUNDED
- **Post-T408 status**: LIVE BUT NOT YET BOUNDED (unchanged)
- **What T406–T408 changed**: Nothing.
- **Assessment**: Two slices shipped (TASK_399, TASK_400). No third slice designed. The messaging design corpus (7 documents) provides the framework, but the next bounded step has not been identified. Lower priority than AAT convergence because it has less structural urgency.

### F. Proof/Export and External-Defensibility Residue
- **Prior status**: PARTIALLY CONSUMED (subsumed by record-to-packet)
- **Post-T408 status**: **FURTHER CONSUMED**
- **What T406 changed**: By landing `governance_evidence.replay_outcome` in both summary surfaces, T406 consumed the most concrete proof/export coherence gap — the one that made external consumers parse raw inner artifacts to determine governance outcome.
- **What remains**: Field-shape normalization (`packet_hash` representation inconsistency), broader export contract convergence, external validator operator hardening. All incremental, none strategic.
- **Assessment**: This is not a standalone direction. Remaining residue can be addressed incrementally if needed; none of it represents a next step-change.

### G. Combo A Structured Summary Emission
- **Prior status**: LIVE BUT NOT YET BOUNDED (newly unblocked by T405)
- **Post-T408 status**: LIVE BUT NOT YET BOUNDED (unchanged)
- **What T406–T408 changed**: Nothing directly. However, T406's `governance_evidence.replay_outcome` establishes a pattern for semantic outcome extraction from enclosed artifacts that could inform Combo A summary design.
- **Assessment**: `verify-chain.py` still emits text-line output, not structured JSON. A design spec defining the summary schema, emission target, and integration with Gate C output would be needed before implementation. Real but not the most strategic next move.

### H. Deployment / Operationalization Residue
- **Prior status**: CONSUMED
- **Post-T408 status**: CONSUMED (unchanged)
- **Assessment**: No new evidence supports reopening.

---

## 4) Classification Summary

| Direction | Classification |
|---|---|
| FS_PROMOTE | **CONSUMED** (full EPIC_PROMOTION.md implemented) |
| Record-to-packet governance evidence coherence | **PARTIALLY CONSUMED** (core replay-outcome shipped; residue is incremental) |
| Post-selector doctrine continuation | PARTIALLY CONSUMED (highest-leverage work shipped in T405) |
| AAT / Foundation v0 admissibility convergence | **LIVE BUT NOT YET BOUNDED** (needs formulation) |
| Messaging follow-on | LIVE BUT NOT YET BOUNDED (no third slice scoped) |
| Proof/export external-defensibility residue | FURTHER CONSUMED (subsumed by T406 + incremental residue) |
| Deployment / operationalization residue | CONSUMED |
| Combo A structured summary emission | LIVE BUT NOT YET BOUNDED (needs design spec) |
| Generic GovMCP maturity | STALE — do not pursue |
| Generic observability / traceability | CONSUMED |
| Demonstration packaging | LOW-YIELD / DEFER |

---

## 5) Recommended Next Strategic Direction

**AAT / Foundation v0 admissibility convergence.**

### Why it wins now

1. **The two strongest implementation-ready lanes are consumed.** The prior broad-state view recommended record-to-packet coherence (#1) and FS_PROMOTE (#2) as the top two directions. T406 consumed the core of record-to-packet coherence. T407+T408 fully consumed FS_PROMOTE. The board has changed: what was formulation-grade (#3 and below) is now the field.

2. **Highest remaining structural leverage.** AAT/Foundation v0 convergence addresses the gap between the implemented AAT subsystem (validators, gates, profiles, shim) and the rest of the governance pipeline. Making these compose into a coherent operator-facing story is the most architecturally meaningful remaining work — it's the difference between "governance components that individually pass tests" and "a governance system an operator can deploy with confidence."

3. **Real repo evidence backs it.** Core AAT implementation is extensive on main: kernel/mechanical/consistency/property validators, Gate A, Gate B ledger, Gate C wrapper, `CORE_GENERIC` and `TOOL_EXEC` profiles, Foundation v0 admissibility gate, shim integration, golden-pass and golden-fail fixtures. The infrastructure exists; what's missing is the convergence story that ties it together.

4. **The design backlog ranked it #1.** `GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md` selected AAT convergence as the immediate formulation winner, with post-selector doctrine continuation as backup. The doctrine continuation backup was partially consumed by T405. AAT convergence has not been addressed at all since that ranking.

5. **Not design-blocked in the hard sense.** It needs formulation (bounded convergence spec), not fundamental research. The building blocks are on main. The formulation work is to define the convergence scope, the operator-facing contract, and the acceptance criteria — then dispatch.

### Why this is formulation, not immediate implementation

AAT convergence needs a bounded spec before Codex can implement it. The blocking question from the design backlog remains: "What bounded operator-facing story defines the convergence workfront (entry criteria, responsible surfaces, success metrics)?" Answering this question is the next control step.

### Runner-up

**Combo A structured summary emission** — if the product owner determines that structured chain-verification output (JSON from `verify-chain.py`) is more urgent than AAT convergence. Would need a design spec first. Lower structural leverage but well-bounded once designed.

### Why not record-to-packet residue

The remaining record-to-packet items (coverage-stamp cross-check, field-shape normalization, record-count sub-fields) are incremental coherence improvements, not a strategic step-change. They can be addressed in a future cleanup tranche without blocking higher-leverage work.

---

## 6) What Is Explicitly Deprioritized

1. **Record-to-packet governance evidence residue**: Core shipped in T406. Remaining items are incremental. Do not treat as a strategic direction.

2. **FS_PROMOTE follow-on**: Fully consumed. Do not reopen unless product requests extensions.

3. **Post-selector doctrine continuation**: Highest-leverage work shipped in T405. Remaining items (multi-case, structural feedback, triage exhaustion) are explicitly deferred in RDD v1. Combo A summary emission is the only non-deferred residue and is lower priority than AAT convergence.

4. **Messaging follow-on**: No third slice designed. Lower structural urgency than AAT convergence.

5. **Generic GovMCP maturity**: Stale framing per canon. Do not pursue.

6. **Proof/export broader hardening**: Incremental residue subsumed by T406 consumption. Not standalone.

7. **Demonstration packaging / workflow follow-on**: Low-yield, downstream.

---

## 7) Evidence That Would Overturn The Recommendation

1. **Product decides structured chain output is more urgent than AAT convergence**: If Combo A structured summary emission is the real product need, produce a bounded design spec and dispatch that instead.

2. **AAT convergence is already sufficient**: If analysis shows that the existing AAT implementation (validators + gates + profiles + shim) already composes into a sufficient operator story, the convergence "gap" is illusory and a different direction should be selected.

3. **Record-to-packet residue is actually blocking external consumers**: If external consumers cannot function without coverage-stamp cross-check or field-shape normalization, those items should be prioritized over AAT convergence.

4. **A new unconsumed design candidate emerges**: If a clearly higher-leverage, clearly bounded direction is identified that was not visible in the current corpus.

5. **Messaging follow-on becomes urgent**: If external pressure (compliance, integration requirements) makes a third messaging slice the blocking need.

6. **T405/T406/T407/T408 surfaces fail in practice**: If any of the recently landed surfaces (Category 6 trigger, terminal judgment, replay_outcome, FS_PROMOTE) reveal runtime problems requiring immediate follow-on.

---

## 8) Net Strategic Position After T405–T408

The four-tranche sequence T405–T408 was a high-velocity execution phase that consumed the two strongest implementation-ready directions and partially consumed a third. The project is now back in formulation mode — not because of stagnation, but because the ready inventory has been harvested.

**Before T405**: Two implementation-ready lanes (record-to-packet coherence, FS_PROMOTE), one design-blocked lane (post-selector doctrine), and several live-but-unbounded directions.

**After T408**: Both implementation-ready lanes consumed. Post-selector doctrine partially consumed. The remaining field is entirely formulation-grade work: live-but-unbounded directions that need bounding specs before implementation can proceed.

The honest next move is formulation of the AAT / Foundation v0 admissibility convergence spec, which the design backlog has ranked #1 since before T405 and which has not been addressed in the intervening execution phase.
