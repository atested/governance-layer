# AAT / Foundation v0 Admissibility Convergence Spec v1

Base SHA: `54e4cf9fa849879e7ddfd474cfe86fbac7c128a5`
Date: 2026-03-17

---

## 1) Objective

Determine whether there is a real bounded convergence lane between the already-landed AAT subsystem and Foundation v0 admissibility, and if so, package it cleanly for future tranche selection. If not, say so and redirect.

---

## 2) What Is Already Implemented On Main

### AAT subsystem (complete operator path)
- **4 validators**: kernel (`K1–K5`), mechanical (`M1`), consistency (`C1–C3`), property (`P1–P2`)
- **2 profiles**: `CORE_GENERIC` (default), `TOOL_EXEC` (elevated consistency enforcement)
- **Profile registry**: deterministic selection via `--profile` or `method_binding.action_kind`
- **Gate A**: `aat-admissibility-gate.sh` → `aat_main.py` → ADR (PASS / FAIL_NON_ADMISSIBLE / FAIL_HARD_STOP)
- **Gate B**: `aat_gate_b_append.py` → appends 2 deterministic events to Foundation v0 process ledger per invocation
- **Gate C**: `aat-gate-c-wrapper.sh` → composes Gate A + Gate B into one operator output contract (STATUS/REASON_CODE/LEDGER_APPENDED)
- **Shim integration**: `validate-proof-bundle.sh` runs Gate C inline when `AAT_SHIM_ENABLE=1`, with strict/advisory modes
- **Staging helper**: `aat_stage_into_proof_bundle.py` — stages AAT objects into proof bundles
- **Operator pilot**: documented workflow for shim invocation without editing hot scripts
- **7 AAT schemas**: input manifest, method binding, constraint set digest, constraint acknowledgment map, claims evidence map, assumptions unknowns register, admissibility decision record
- **Extensive test coverage**: 19 system tests covering kernel, integration, determinism, profiles, shim strictness, stop disambiguation, outcome markers, code extraction, bundle alignment, operator pilot

### Foundation v0 subsystem (complete process-level gate)
- **Process ledger**: `foundation_v0_process_ledger.py` — append + verify modes with chain integrity, entry hash verification, sequence enforcement, coverage stamp validation, surface coverage checking
- **Admissibility gate**: `foundation-v0-admissibility-gate.sh` — composes proof-bundle verification + ledger verification; emits ADMISSIBLE/NON_ADMISSIBLE/STOP_REQUIRED
- **Surface catalog**: 8 capability surfaces (filesystem, memory, model, network, routing, shell, toolchain, web)
- **Typed ref catalog**: 5 ref types (decision_record, proof_bundle, rules_version, input_file, action_decision_record)
- **Normalization and probing**: `foundation-v0-admissibility-normalize.sh`, `foundation-v0-bundle-probe.sh`
- **Test coverage**: process ledger, admissibility gate, normalization, bundle probe tests

### The connection between AAT and Foundation v0
Gate B (`aat_gate_b_append.py`) writes AAT decision events directly into the Foundation v0 process ledger using `foundation_v0_process_ledger.py append`. The connection is:
1. Gate B maps `action_kind` to `capability_surfaces` (e.g., `CORE_GENERIC` → `["toolchain"]`, `TOOL_EXEC` → `["shell"]`)
2. Gate B requires the `action_decision_record` typed ref type in the catalog
3. Foundation v0 verify checks chain integrity, entry hashes, and surface coverage for all ledger entries, including AAT-originated ones
4. Coverage stamp cross-check ensures ledger surfaces are a subset of stamp surfaces

**This connection is already implemented and tested.** Gate B writes; Foundation v0 verifies. The typed ref catalog includes both standard governance refs and the AAT-specific `action_decision_record` type. The surface catalog is shared.

---

## 3) What Convergence Gap Was Hypothesized

The design backlog (`GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`) identified "AAT / Foundation v0 admissibility convergence restock candidate" as the #1 formulation winner. The blocking question: "What bounded operator-facing story defines the convergence workfront?"

Three candidates were evaluated on main:

### Candidate A — Foundation Policy Registry Tie-In
**Conclusion on main** (`AAT_FOUNDATION_REGISTRY_TIEIN_FORMULATION__v1.md`): **NOT DISTINCT ENOUGH.** No concrete mapping artifact exists. Inventing one would duplicate consumed Gate C semantics. Collapses into reinterpretation of existing outputs.

### Candidate B — Admissibility Evidence Exchange Contract
**Conclusion on main** (`AAT_FOUNDATION_CONVERGENCE_FORMULATION__v1.md`): **NOT DISTINCT ENOUGH.** No concrete evidence artifacts proposed. Without them, duplicates consumed work.

### Candidate C — Operator-Facing Convergence Runbook
**Conclusion on main** (`AAT_FOUNDATION_CONVERGENCE_FORMULATION__v1.md`): Conditionally distinct if new decision points and acceptance proofs are defined, but less precise than Candidate A.

---

## 4) Did T405–T408 Change Anything About This Conclusion?

**No.** T405–T408 changed zero files in the AAT or Foundation v0 subsystems:
- T405 landed in the RDD lane (Category 6 + terminal judgment)
- T406 landed in the proof-packet/bundle-validator summary lane (replay_outcome)
- T407 landed in the FS_PROMOTE policy evaluation lane
- T408 landed in the FS_PROMOTE execution lane

The convergence formulation's NOT DISTINCT ENOUGH conclusions remain unaffected.

---

## 5) Honest Assessment: Is There A Real Convergence Gap?

### What convergence would mean
"Convergence" between AAT and Foundation v0 would mean: a new artifact, contract, or behavior that makes the AAT-to-Foundation connection tighter, more operator-visible, or more verifiable than it already is.

### What already exists
The connection is already tight:
- **Data flow**: Gate B writes AAT decisions to the Foundation v0 process ledger with typed refs, capability surface mappings, and deterministic hashing.
- **Verification**: Foundation v0 verify checks AAT-originated entries for chain integrity, hash parity, and surface coverage — identical treatment to any other ledger entry.
- **Operator path**: Gate C composes the entire AAT pipeline (validators → Gate A → Gate B → ledger) into a single operator-facing command with deterministic output. The shim integrates this into validate-proof-bundle.
- **Schema alignment**: The typed ref catalog and surface catalog are shared by both subsystems.

### What is missing
To honestly evaluate whether a gap exists, I checked for:

1. **Does Foundation v0 verify know it's verifying AAT-originated entries?** No — and this is by design. Foundation v0 verification is entry-type-agnostic. It verifies chain integrity and hash parity regardless of entry origin. This is a strength, not a gap.

2. **Is there an operator-visible surface showing AAT admissibility status within Foundation v0 verification output?** No — Foundation v0 verify reports per-entry `admissibility_status` and `failure_codes` but does not distinguish AAT-originated entries from other entries. An operator would need to correlate `operation_id` values.

3. **Does the surface mapping (`action_kind` → `capability_surfaces`) have a formal contract?** The mapping exists in `aat_gate_b_append.py:map_action_kind_to_surfaces()` as a hardcoded dict. It is not a separate artifact. But it is tested (profile expansion and integration tests).

4. **Is there a combined gate that runs both AAT + Foundation v0 in one operator invocation?** No. `validate-proof-bundle.sh` has the AAT shim but does not invoke `foundation-v0-admissibility-gate.sh`. They are separate invocations.

### Gap evaluation

| Candidate gap | Is it real? | Is it a step-change? | Is it distinct from consumed work? |
|---|---|---|---|
| Foundation v0 verify doesn't label AAT entries | Entry-type-agnostic is architectural choice, not deficiency | No | Would duplicate Gate B's existing labeling |
| No combined AAT + Foundation v0 gate | Real — two separate invocations exist | **Marginal** — convenience, not new capability | Conditionally distinct if it produces new verification semantics |
| Surface mapping has no formal artifact | Real — hardcoded in Gate B | No — a JSON artifact would be trivially extractable from the existing code | Would duplicate what's already in `map_action_kind_to_surfaces()` |
| AAT outcomes not in Foundation v0 admissibility output | Real — Foundation v0 reports structural verification, not AAT pass/fail | **Marginal** — AAT pass/fail is already available via Gate C | Would need to define new output semantics |

---

## 6) Fail-Closed Conclusion

**The AAT / Foundation v0 convergence lane is NOT BOUNDABLE as a strategic next direction.**

### Why

1. **The connection is already implemented.** Gate B writes to the Foundation v0 ledger. Foundation v0 verifies those entries. The typed ref and surface catalogs are shared. The shim integrates Gate C into validate-proof-bundle. The operator pilot documents how to use it.

2. **The prior on-main formulation already concluded NOT DISTINCT ENOUGH.** Two of three candidates failed the distinctness test. T405–T408 did not change the relevant surfaces.

3. **The residual gaps are marginal, not strategic.** The remaining items (combined gate convenience, surface mapping formalization, AAT outcome labeling in Foundation v0 output) are incremental improvements, not a step-change. None of them would unlock new capability or address a real operator pain point that doesn't already have a workaround.

4. **Forcing a convergence lane would replay consumed work.** Any attempt to define a bounded convergence tranche would need to re-examine Gate B, Gate C, the shim, and the ledger verification — all of which are consumed baseline. The distinctness risk is high.

### What this means for strategic ranking

The broad-state delta after T408 (`GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`) ranked AAT convergence as #1 based on the design backlog's earlier assessment. That earlier assessment was correct at the time — AAT convergence was the top formulation candidate when many other lanes were still live. But the on-main convergence formulation docs then evaluated the candidates and found them not distinct enough. This finding is canonical repo truth that the broad-state delta did not account for because those formulation docs pre-date the broad-state delta's predecessor document.

**The AAT convergence direction should be reclassified from LIVE BUT NOT YET BOUNDED to LOW-YIELD / DEFER.** It is not design-blocked — it was designed, evaluated, and found insufficient.

---

## 7) What Does This Leave As The Next Strategic Direction?

With AAT convergence downgraded, the remaining live directions from the broad-state delta are:

| Direction | Classification | Bounded? |
|---|---|---|
| Combo A structured summary emission | LIVE BUT NOT YET BOUNDED | Needs design spec |
| Messaging follow-on | LIVE BUT NOT YET BOUNDED | No third slice scoped |
| Record-to-packet residue | PARTIALLY CONSUMED | Incremental (coverage stamp cross-check, field normalization, record counts) |
| Post-selector doctrine residue | PARTIALLY CONSUMED | Only Combo A is non-deferred |

### Honest next-move assessment

The field of remaining live directions is thin. All remaining candidates are either:
- **Unbounded formulation-grade** (Combo A, messaging follow-on)
- **Incremental residue** (record-to-packet, proof/export)
- **Explicitly deferred** (post-selector doctrine items beyond Combo A)

The two candidates with the most concrete next step are:

1. **Combo A structured summary emission**: `verify-chain.py` emits text-line output. A bounded tranche could extend it to emit structured JSON summary including governance outcome, chain verification result, and terminal judgment disposition. T405 unblocked this by landing the terminal judgment runtime. Needs a design spec defining the JSON schema and emission contract.

2. **Record-to-packet coherence residue**: The remaining items from the design spec — `coverage_stamp_cross_check`, `replay_record_counts`, `replay_report_version`, and `packet_hash` field-shape normalization — are individually small but collectively complete the coherence contract. Already has a design spec (partially consumed).

Neither of these is a strategic step-change comparable to what T405–T408 delivered. The project may be approaching an honest plateau where remaining work is incremental rather than transformative.

---

## 8) False-Closure Cases

The following would represent false closure of this spec:

1. **Declaring AAT convergence "done" because the connection exists** — the spec's conclusion is that convergence was already evaluated and found not distinct enough, not that it was completed.
2. **Inventing a convergence lane not supported by repo evidence** — no concrete new artifact or contract has been identified that would make the convergence distinct.
3. **Blaming the conclusion on insufficient formulation effort** — the on-main formulation docs tested three candidates rigorously. The conclusion is substantive, not premature.
4. **Treating the marginal gaps as strategic** — combined gate convenience, surface mapping formalization, and outcome labeling are real but do not represent a governance step-change.
5. **Reopening consumed Gate B/C/shim work under a "convergence" label** — this would replay consumed baseline.

---

## 9) Evidence That Would Overturn This Conclusion

1. **A new concrete operator pain point**: If an actual operator attempting to use the AAT + Foundation v0 pipeline in practice encounters a gap that cannot be worked around with existing tooling — that would be real evidence for a convergence tranche.

2. **External compliance requirement**: If a compliance or audit framework requires a single unified admissibility statement that composes AAT and Foundation v0 results — that would be a real new contract need.

3. **A new capability surface**: If a new governed tool or domain is added that requires the AAT-to-Foundation mapping to be extended (e.g., new `action_kind` → `capability_surfaces` entries) — that could justify a bounded registry extension.

4. **Product decision to merge AAT and Foundation v0 into one gate**: If the product owner decides the two-gate architecture is wrong and they should be unified — that would be a real redesign, not a convergence tranche.

5. **Discovery of a verification gap**: If Foundation v0 verify fails to detect a real AAT integrity problem that Gate B should have prevented — that would be a concrete bug or contract gap.
