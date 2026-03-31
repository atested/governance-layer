# Current-Main Governance Broad-State Delta Refresh After T405 v1

Base SHA: `71ebff418c9810099b96f590831a089b7b6fe1d0`
Prior broad-state baseline: `DESIGN_TO_REPO_GAP_AUDIT__v1.md` at `1feb9ea3`
Date: 2026-03-17

---

## 1) What Materially Changed On Main Because Of T405

T405 landed the following on main (M139):

1. **Category 6 case class (genuine_residual)**: `policy-eval.py` now emits `UNDECIDED` for FS_COPY when `intent.constraints.requires_authorization: true`, no policy violations exist, and destination-exists is not triggered. This is the second UNDECIDED case class — the first being Category 1 (dest-exists-no-overwrite structural deficiency).

2. **Terminal judgment runtime**: `scripts/terminal-judgment-eval.py` — a standalone emitter analogous to `triage-eval.py`, with 8 validation rules, Ed25519 signing, chain append, and `policy_decision` bridge field.

3. **Terminal judgment disposition taxonomy**: Three outcomes (ALLOW, DENY, NON_RESOLUTION) and four methods (`human_authority`, `bounded_estimation`, `random_tiebreak`, `non_resolution`) with method-to-outcome constraints.

4. **RDD-to-Gate-C bridge**: `policy_decision` on terminal judgment mirrors `outcome`; Gate C consumes it as a normal decision record without modification.

5. **Category 6 triage criteria**: `rdd_triage_criteria.v1.json` now includes `fs_copy_authorization_required` with `genuine_residual` finding, `ESCALATION_JUSTIFIED` disposition, and `human_authority` method.

6. **3-record chain coverage**: Full pass(UNDECIDED) → triage(ESCALATION_JUSTIFIED) → terminal(ALLOW) chain verified by `verify-chain.py`. 13-case test suite with 3 fail-closed negative controls.

---

## 2) Did T405 Merely Consume One Lane, Or Shift Strategic Rankings?

**T405 shifted strategic rankings.** It did not merely check a box on one doctrinal lane. The changes matter because:

### What was unblocked
- The gap audit (`DESIGN_TO_REPO_GAP_AUDIT__v1.md`) classified **RDD Terminal Judgment Runtime** as UNIMPLEMENTED (row 1B, priority Low/deferred) and **RDD Second Case Class** as UNIMPLEMENTED (row 1C, priority Low). Both are now implemented.
- The Combo A clarification (`COMBO_A_CHAIN_VERIFICATION_RUNTIME_DESIGN_CLARIFICATION__v1.md`) classified chain verification as **STILL_NOT_IMPLEMENTABLE** due to 3 missing prerequisites: terminal judgment runtime, disposition taxonomy, and RDD-to-Gate-C bridge. All three are now resolved.
- The design backlog (`GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`) ranked "Post-selector doctrine continuation" as the #2 formulation candidate, noting it was **design-blocked**. The blocking design questions (which doctrinal surface? what dispositions? what is the emitter contract?) are now answered and implemented.

### What was NOT unblocked
- Combo A structured summary emission (`chain_verification_summary.json`) is still not implemented. `verify-chain.py` emits text-line output, not structured JSON. However, the prerequisite blocker (missing terminal judgment) is now removed.
- Multi-case triage orchestration remains deferred.
- Structural Feedback Function remains deferred.

### Net ranking shift
The "post-selector doctrine continuation" lane moved from **design-blocked** to **partially consumed** — its first bounded post-selector tranche shipped. The design backlog's #1 winner (AAT / Foundation v0 admissibility convergence) was not affected by T405 and remains live-but-unbounded. The record-to-packet governance evidence coherence design remains live and implementation-ready.

---

## 3) Reassessment Of Major Directions

### A. Post-Selector Doctrine Continuation
- **Prior status**: Design-blocked (#2 formulation candidate in design backlog)
- **Post-T405 status**: PARTIALLY CONSUMED
- **What shipped**: Category 6 case class, terminal judgment runtime, disposition taxonomy, RDD-to-Gate-C bridge, 3-record chain verification
- **What remains**:
  - Combo A structured summary emission (JSON from `verify-chain.py`) — now unblocked but not yet implemented or designed as a bounded tranche
  - Multi-case triage orchestration — still deferred
  - Structural Feedback Function — still deferred
  - Formal triage exhaustion verification — still deferred
  - Second tool domain beyond FS_COPY — still deferred
- **Assessment**: The highest-leverage post-selector work is done. What remains is either incremental (summary emission) or explicitly out of v1 scope. This lane is no longer a strategic priority unless product decides to extend RDD to additional tools or domains.

### B. Record-to-Packet Governance Evidence Coherence
- **Prior status**: Strongest formulation winner, underdesigned (gap audit row 4A, "most important underdesigned area")
- **Post-T405 status**: LIVE AND BOUNDED — design spec exists (`RECORD_TO_PACKET_GOVERNANCE_EVIDENCE_COHERENCE_DESIGN__v1.md`), acceptance criteria defined (10 must-pass, 5 must-not), implementation does not depend on T405 surfaces
- **What T405 changed**: Nothing directly. T405 did not touch proof-packet, replay, or bundle-validation surfaces.
- **Assessment**: This lane is now the strongest implementation-ready candidate. It has a complete design spec, bounded scope (summary-surface changes only), clear acceptance criteria, and explicit distinctness from consumed work. It does not need further formulation — it needs implementation dispatch.

### C. AAT / Foundation v0 Admissibility Convergence
- **Prior status**: #1 formulation winner in design backlog, live-but-unbounded
- **Post-T405 status**: LIVE BUT NOT YET BOUNDED — unchanged
- **What T405 changed**: Nothing directly. T405 is RDD-lane; AAT convergence is a separate concern.
- **Assessment**: Still needs formulation work to define what "convergence" means as a bounded spec. The design backlog's blocking question remains: "What bounded operator-facing story defines the convergence workfront?" No answer has been produced since that question was posed.

### D. Messaging Follow-On
- **Prior status**: Live-but-unbounded, noted for future formulation
- **Post-T405 status**: LIVE BUT NOT YET BOUNDED — unchanged
- **What T405 changed**: Nothing.
- **Assessment**: Two slices shipped (TASK_399, TASK_400). No third slice is designed or scoped. The lane remains lower priority than B and C because it has less repo evidence supporting a next move.

### E. Proof/Export and External-Defensibility Residue
- **Prior status**: Core seams landed, broader hardening live-but-unbounded
- **Post-T405 status**: PARTIALLY CONSUMED (unchanged by T405)
- **What T405 changed**: Nothing directly. However, if record-to-packet governance evidence coherence (lane B) ships, it would partially consume additional proof/export residue.
- **Assessment**: This is not a standalone strategic direction. Its remaining value is subsumed by lane B (which addresses the summary-surface coherence gap) and by incremental hardening that can follow later.

### F. Deployment / Operationalization Residue
- **Prior status**: Consumed (deployment execution-path and packaging families)
- **Post-T405 status**: CONSUMED — unchanged
- **Assessment**: No new repo evidence supports reopening this. External validator/operator hardening residue exists but is not bounded.

### G. FS_PROMOTE
- **Prior status**: Designed-and-unimplemented (gap audit row 1A, fully designed, medium priority)
- **Post-T405 status**: DESIGNED AND UNIMPLEMENTED — unchanged
- **What T405 changed**: Nothing.
- **Assessment**: Full design exists in `EPIC_PROMOTION.md`. Could become an implementation tranche immediately if prioritized. Not strategically transformative but practically useful.

### H. Combo A Structured Summary Emission
- **Prior status**: Design-blocked (depended on terminal judgment runtime)
- **Post-T405 status**: UNBLOCKED BUT UNBOUNDED — the prerequisite (terminal judgment) now exists, but no bounded design spec for the summary schema or emission path has been produced
- **Assessment**: This is a real newly-unblocked direction. It would extend `verify-chain.py` to emit structured JSON summary including governance outcome. It could be a small bounded tranche but needs a design spec first.

---

## 4) Classification Summary

| Direction | Classification |
|---|---|
| Post-selector doctrine continuation | PARTIALLY CONSUMED |
| Record-to-packet governance evidence coherence | LIVE AND BOUNDED (implementation-ready) |
| AAT / Foundation v0 admissibility convergence | LIVE BUT NOT YET BOUNDED |
| Messaging follow-on | LIVE BUT NOT YET BOUNDED |
| Proof/export external-defensibility residue | PARTIALLY CONSUMED (subsumed by B) |
| Deployment / operationalization residue | CONSUMED |
| FS_PROMOTE | LIVE AND BOUNDED (implementation-ready) |
| Combo A structured summary emission | LIVE BUT NOT YET BOUNDED (newly unblocked) |
| Generic GovMCP maturity | STALE — do not pursue |
| Generic observability / traceability | CONSUMED |
| Demonstration packaging | LOW-YIELD / DEFER |

---

## 5) Recommended Next Strategic Direction

**Record-to-packet governance evidence coherence (lane B).**

### Why it wins now

1. **Implementation-ready**: Complete design spec exists with 10 must-pass acceptance criteria, 5 must-not constraints, and explicit distinctness verification. No further formulation needed.

2. **Product-legible step-change**: Moves the project from "structurally intact proof packets" to "proof packets that tell you whether governance actually passed." This is the kind of output external consumers and compliance reviews care about.

3. **No T405 dependency or conflict**: Operates entirely on proof-packet/bundle-validation surfaces. Does not reopen RDD, messaging, or AAT.

4. **Bounded scope**: Summary-surface changes only. No new scripts, no schema changes, no new record types. Existing test infrastructure covers the pipeline; new tests validate governance-outcome propagation.

5. **Unblocks future lanes**: Once governance evidence is coherent at the summary level, later work (Combo A summary emission, AAT convergence, broader export hardening) has a proven pattern to follow.

### Runner-up

**FS_PROMOTE** — if the product owner needs cross-root promotion capability more urgently than evidence coherence. Full design exists, implementation could proceed immediately. Not as strategically transformative but practically useful.

### Backup formulation candidate

**Combo A structured summary emission** — newly unblocked by T405. Would need a bounded design spec (summary schema, emission target, integration with Gate C output) before implementation. Lower priority than lane B because it requires design work first.

---

## 6) What Is Explicitly Deprioritized

1. **Post-selector doctrine continuation**: T405 shipped the highest-leverage post-selector tranche. What remains (multi-case, structural feedback, triage exhaustion) is explicitly deferred in RDD v1 and should not be reopened without product decision.

2. **AAT / Foundation v0 admissibility convergence**: Still needs formulation. The blocking design question from the design backlog remains unanswered. Should not be dispatched as implementation until a bounded convergence spec exists.

3. **Messaging follow-on**: No third slice is designed or scoped. Lower priority than implementation-ready lanes.

4. **Generic GovMCP maturity**: Stale framing per canon. Do not pursue.

5. **Demonstration packaging / workflow follow-on**: Low-yield, downstream concern.

---

## 7) Evidence That Would Overturn The Recommendation

1. **Product decides cross-root promotion is urgent**: If FS_PROMOTE is needed now, dispatch it directly — the design is complete.

2. **Combo A structured summary is the real product need**: If the product owner determines that structured chain-verification output (not proof-packet evidence coherence) is the next step-change, then produce a bounded design spec for Combo A summary emission and dispatch that instead.

3. **Record-to-packet coherence is already sufficient**: If analysis shows that external consumers do not actually need governance outcome in summary surfaces — that parsing `replay_audit_report.json` directly is acceptable — then the "gap" is illusory and a different direction should be selected.

4. **AAT convergence becomes urgent**: If compliance or Foundation v0 integration creates external pressure, AAT convergence should be formulated and prioritized.

5. **A new unconsumed design candidate emerges**: If a clearly higher-leverage, clearly bounded design direction is identified that was not visible in the current corpus.

6. **T405 surfaces fail in practice**: If the Category 6 trigger or terminal judgment emitter reveals runtime problems that require immediate follow-on work within the RDD lane.
