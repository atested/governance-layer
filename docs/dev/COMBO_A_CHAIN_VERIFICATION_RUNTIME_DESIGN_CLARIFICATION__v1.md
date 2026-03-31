# Combo A Chain Verification — Runtime Design Clarification v1

Base SHA: `fc065503d27fff98b275b84ec699b8525d4cb279`
Status: RUNTIME DESIGN CLARIFICATION
Lane: post-selector doctrine continuation
Derived from: current-main repo evidence only

## Authoritative Input Status

The following documents were referenced in the originating dispatch as authoritative inputs. **None exist on current main or on any remote branch:**

| Document | Status |
|---|---|
| `docs/dev/POST_SELECTOR_DOCTRINE_FORMULATION__v1.md` | ABSENT |
| `docs/dev/CHAIN_VERIFICATION_TERMINAL_JUDGMENT_SPEC__v1.md` | ABSENT |
| `docs/dev/CHAIN_VERIFICATION_TRANCHE_SELECTION__v1.md` | ABSENT |
| `docs/dev/CHAIN_VERIFICATION_COMBO_A_SPEC__v1.md` | ABSENT |
| `docs/dev/CHAIN_VERIFICATION_IMPL_SURFACE__v1.md` | ABSENT |

This artifact is derived entirely from current-main repo evidence. No prior "Combo A" or "chain verification summary" concept exists in the codebase.

## 1) Current Combo A Runtime Baseline

"Combo A" as described in the dispatch means: verify that a chain of `UNDECIDED pass → triage → terminal judgment (PASS-equivalent) → Gate C (PASS)` holds.

### What exists on current main

| Surface | Script | Status |
|---|---|---|
| UNDECIDED pass emission | `scripts/policy-eval.py` | Landed (Phase 1) |
| Triage evaluation | `scripts/triage-eval.py` | Landed (Phase 2) |
| Chain ordering verification | `scripts/verify-chain.py` | Landed (Phase 3), validates pass→triage→terminal ordering, linkage, and coverage stamp |
| Signal extraction | `scripts/extract-rdd-signals.py` | Landed (Phase 4) |
| Replay of triage/terminal | `scripts/replay-record.py` | Landed (Phase 5), validates deterministic integrity invariants for `triage_decision` and `terminal_judgment` record types |
| Gate C composition | `system/scripts/aat-gate-c-wrapper.sh` | Landed, composes Gate A (admissibility) + Gate B (ledger append) |
| Terminal judgment emitter | — | **Does not exist** |
| Terminal judgment dispositions | — | **Undefined** beyond schema fields; sole fixture uses `NON_RESOLUTION` |
| RDD chain → Gate C bridge | — | **Does not exist** |
| `chain_verification_summary.json` | — | **Does not exist** as a concept or emission target |

### What the RDD v1 plan explicitly defers

From `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`, section "Explicitly out of scope for v1":

> - Terminal Judgment runtime implementation
> - Structural Feedback Function analysis
> - Multi-domain support
> - Multi-case-class Triage

Terminal judgment runtime is not an oversight — it is an intentional v1 deferral.

## 2) Required Question Answers

### Q1: What exact runtime surface should own Combo A verification?

**CANNOT BE SPECIFIED CONCRETELY.**

The natural candidate would be `scripts/verify-chain.py`, which already validates chain ordering and linkage. However, `verify-chain.py` currently:
- Emits only text-line output (`PASS: chain verified (N records)` + coverage lines)
- Does not emit structured JSON summary
- Does not evaluate terminal judgment disposition semantics (it checks ordering only — "is terminal after triage?" — not outcome — "did the terminal judgment resolve the case?")
- Has no concept of "chain passed governance verification" as distinct from "chain has correct structural ordering"

Extending `verify-chain.py` to own Combo A verification is architecturally reasonable but requires:
- A terminal judgment disposition taxonomy (what dispositions mean PASS vs NON_RESOLUTION vs FAIL?)
- A structured summary emission path
- A decision about whether Gate C outcome is part of chain verification or a separate post-verification step

None of these decisions can be made without the missing terminal judgment design.

### Q2: What exact file or files should emit `chain_verification_summary.json`?

**CANNOT BE SPECIFIED CONCRETELY.**

If the terminal judgment design existed, the natural answer would be: `scripts/verify-chain.py` emits `chain_verification_summary.json` to stdout or a file path, containing:
- chain structural validity (existing capability)
- terminal judgment disposition outcome (requires new design)
- coverage stamp aggregate (existing capability)

But the summary schema itself depends on the terminal judgment disposition taxonomy, which does not exist.

### Q3: What exact existing artifacts/records are sufficient now?

| Artifact | Status | Sufficient? |
|---|---|---|
| Triage record | Exists — emitted by `triage-eval.py` with full schema | YES |
| Terminal record | Schema defined, one test fixture exists (`rdd_phase5_replay_valid_terminal.json`) with `NON_RESOLUTION` disposition | NO — no emitter, no PASS-equivalent disposition defined |
| Gate C history | Exists — `aat-gate-c-wrapper.sh` emits STATUS/REASON_CODE/LEDGER_APPENDED | YES for Gate C itself, but NO for connection to RDD chain |
| Replay/audit evidence | Exists — `replay-record.py` supports triage and terminal replay | YES for integrity verification |

### Q4: What minimal new runtime support is actually required?

To implement Combo A chain verification, the following would be needed:

1. **Terminal judgment emitter** — a script analogous to `triage-eval.py` that takes a triage record and produces a terminal judgment record. This is the single largest missing piece.

2. **Terminal judgment disposition taxonomy** — what dispositions exist beyond `NON_RESOLUTION`? The dispatch references "terminal PASS" but no design defines what disposition value constitutes a PASS. The sole existing fixture uses `judgment_method: "NON_RESOLUTION"` and `disposition.type: "NON_RESOLUTION"`.

3. **Structured summary emission from verify-chain.py** — extend the verifier to emit JSON summary including governance outcome, not just structural ordering checks.

4. **RDD-to-Gate-C bridge decision** — Gate C currently takes `--action-record`, `--decision-record`, `--ledger`. The RDD chain produces `pass_decision`, `triage_decision`, `terminal_judgment` records. Which record maps to which Gate C input? This mapping does not exist.

### Q5: What minimal fixtures or test-data support is required?

- A valid 3-record chain fixture: pass(UNDECIDED) → triage(DEFER) → terminal(PASS-equivalent)
- A valid 3-record chain fixture with terminal NON_RESOLUTION (should not count as chain PASS)
- Gate C input fixtures derived from RDD chain output
- Invalid-chain negative fixtures (terminal before triage, etc. — some already exist)

### Q6: Can the tranche still be implemented as one bounded task?

**NO.** The tranche requires at minimum:

1. **Design task**: Terminal judgment disposition taxonomy and emitter contract specification
2. **Design task**: RDD chain → Gate C bridge mapping
3. **Implementation task**: Terminal judgment emitter
4. **Implementation task**: Structured summary emission from verify-chain.py
5. **Implementation task**: Integration wiring and fixtures

Items 1-2 are **design-blocked** — they cannot be resolved by implementation judgment alone. They require product decisions about what terminal judgment dispositions mean.

### Q7: What should be explicitly excluded?

| Exclusion | Why |
|---|---|
| Consumed selector-mode work (Phases 7-14) | Already landed and bounded; Combo A does not reopen it |
| Multi-case orchestration | RDD v1 is bounded to FS_COPY dest-exists-no-overwrite; Combo A must stay in that boundary |
| Broad doctrine redesign | The disposition taxonomy needs a narrow v1 answer, not a general theory of terminal judgment |
| AAT/proof-export work | Gate C is an existing AAT surface; extending it to consume RDD output is distinct from proof-export coherence work |
| Structural Feedback Function | Explicitly deferred in RDD v1 |

## 3) Classification

**STILL_NOT_IMPLEMENTABLE**

### Why

The Combo A chain verification tranche cannot be implemented because it depends on design decisions that have not been made and are not derivable from current-main evidence:

1. **Terminal judgment runtime is explicitly deferred** in the authoritative RDD v1 implementation plan. This is not ambiguity — it is a deliberate scope exclusion. Implementing Combo A requires reversing this decision.

2. **No terminal judgment disposition taxonomy exists.** The dispatch references "terminal PASS" but current main defines no disposition value that constitutes PASS. The only existing fixture uses `NON_RESOLUTION`. This is a product decision, not an implementation detail.

3. **No RDD-to-Gate-C bridge exists or is designed.** Gate C operates on action/decision records with `--action-record`, `--decision-record`, `--ledger` arguments. The RDD chain produces `pass_decision`, `triage_decision`, `terminal_judgment` records. No mapping between these two systems exists. This is an architectural decision, not an implementation detail.

4. **`chain_verification_summary.json` has no schema.** The summary's content depends on the terminal judgment disposition taxonomy (point 2), which doesn't exist.

These are not obstacles that "two more Codex runs" will overcome. They are prerequisite design decisions.

## 4) What Would Make This Implementable

A bounded design spec answering:

1. **Terminal judgment dispositions**: What values can `disposition.type` take? Which constitute PASS? Which constitute FAIL? Is NON_RESOLUTION a third terminal state?

2. **Terminal judgment emitter contract**: What inputs does it take? (Triage record only? Triage + external evidence?) What validation does it perform? Is it deterministic or judgmental?

3. **RDD chain → Gate C mapping**: Which RDD record maps to Gate C's `--action-record`? Which maps to `--decision-record`? Or does Gate C not apply to RDD chains at all, and "Combo A" means something other than "pipe terminal judgment into Gate C"?

4. **Chain verification summary schema**: What fields? What governance-outcome semantics? Does it include Gate C result or is Gate C a separate post-verification step?

If these four questions were answered in a bounded spec, the implementation could likely proceed as two tasks:
- Task A: Terminal judgment emitter + fixtures
- Task B: Chain verification summary emission + Gate C integration (if applicable)

## 5) Recommended Next Control Step

**Do not attempt another implementation task for Combo A.**

Instead: produce a bounded terminal judgment disposition + emitter design spec (answering questions 1-4 above), treating it as the next doctrine continuation pass within the post-selector RDD lane.

This aligns with `docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`, which identifies "Post-selector doctrine continuation requiring bounded restock" as the #2 formulation candidate and asks exactly the right blocking question:

> Which doctrinal surface (e.g., triage evaluator, chain verification, external proof interplay) should the next continuation address, and what are its success criteria/dry-run acceptance cases?

The answer from this analysis: **chain verification via terminal judgment** is the next doctrinal surface, and the blocking design questions are specified above.

## 6) Evidence That Would Overturn This Recommendation

- Discovery of an existing terminal judgment disposition taxonomy or emitter design in an unexamined artifact
- A product decision that Combo A does not actually require terminal judgment runtime (e.g., Combo A is redefined to mean something verifiable with only pass + triage records)
- A product decision that Gate C is not part of Combo A (simplifying the scope to chain verification only)
- An external spec that resolves the RDD-to-Gate-C mapping question
