# Residual Discretion Doctrine — v1 Implementation Plan

**Status**: [ACTIVE] — Phases 1–11 implementation seams landed on main; next seam requires bounded restock/spec determination
**Date**: 2026-03-10
**Author**: Cecil (governance operator), directed by Greg (product owner)
**Schema contract**: `docs/dev/design-memos/2026-03-08__phase1-schema-package__plan.md` (ACCEPTED)
**Doctrine**: `docs/RESIDUAL_DISCRETION_DOCTRINE.md` (CANDIDATE)

---

## Summary

This plan started as a four-phase v1 sequence. Current main has advanced well beyond that initial table: Phase 0 is accepted and Phases 1–11 seams are landed through task bundles `TASK_311`–`TASK_340`. This document now records landed progression and keeps the next-seam decision bounded.

| Phase | Name | Status | Gate to activate |
|---|---|---|---|
| 0 | Schema Package | ACCEPTED | — |
| 1 | Pass Extension | COMPLETE (LANDED) | Schema accepted (done) |
| 2 | Triage Evaluator | COMPLETE (LANDED) | All Phase 1 tasks merged (done) |
| 3 | Chain Verification Extension | COMPLETE (LANDED) | All Phase 2 tasks merged (done) |
| 4 | Minimal Structural Feedback Plumbing | COMPLETE (LANDED) | All Phase 3 tasks merged (done) |
| 5 | Replay extension for triage/terminal records | COMPLETE (LANDED) | All Phase 4 tasks merged (done) |
| 6 | External triage criteria file | COMPLETE (LANDED) | All Phase 5 tasks merged (done) |
| 7 | Triage criteria selector routing | COMPLETE (LANDED) | All Phase 6 tasks merged (done) |
| 8 | Triage selector contract strictness | COMPLETE (LANDED) | All Phase 7 tasks merged (done) |
| 9 | Selector-mode explicit wiring | COMPLETE (LANDED) | All Phase 8 tasks merged (done) |
| 10 | Selector-mode source contract hardening | COMPLETE (LANDED) | All Phase 9 tasks merged (done) |
| 11 | Selector-mode request-source strictness | COMPLETE (LANDED) | All Phase 10 tasks merged (done) |

---

## Scope Declaration

v1 is bounded to the **FS_COPY dest-exists-no-overwrite case class** in the filesystem domain. Extension to other UNDECIDED case classes requires a separate boundary-extension decision. Landed Phases 1–11 remain bounded to this same case class.

**v1 explicitly defers**:
- Terminal Judgment runtime implementation
- Structural Feedback Function analysis, pattern detection, or proposal generation
- Multi-domain support
- Multi-case-class Triage
- Formal Triage exhaustion verification (doctrine OQ-1)
- Domain calibration framework (doctrine OQ-2)
- Structural Feedback observation scope governance (doctrine OQ-3)
- Feedback evaluation machinery (doctrine Section 10)

---

## Phase 0: Schema Package — ACCEPTED

**Artifact**: `docs/dev/design-memos/2026-03-08__phase1-schema-package__plan.md`

**What was resolved**:
- First UNDECIDED case class: FS_COPY dest-exists-no-overwrite
- UNDECIDED boundary principle: "UNDECIDED iff evaluator has no explicit rule for the condition" (v1 operational test for rule-gap detection; does not foreclose other UNDECIDED conditions for future case classes)
- v0.2 record schemas: Pass, Triage, Terminal Judgment
- Chain-linking: `process_id`, `record_type`, `originating_pass_hash`, `originating_triage_hash`
- `basis_detail`: required and non-empty for judgmental findings; absent for deterministic findings
- IQ-4 (criteria format): hardcoded for v1
- IQ-6 (F2 automation): F2 emitted automatically via standard template, no manual review gate
- IQ-7 (process_id replay): process_id is chain-grouping identifier; replay-compatibility requires stable `GOV_SESSION_ID` at call site (operational practice, not schema change)

---

## Phase 1: Pass Extension — COMPLETE (LANDED)

**Goal**: Extend `policy-eval.py` to emit `UNDECIDED` for the FS_COPY dest-exists case, adding v0.2 schema fields to all records.

**Landed task bundle**: `TASK_311`, `TASK_312`, `TASK_313` (see `docs/dev/tasks/ready/`)

**Workfront branch**: `codex/RDD_PASS_UNDECIDED__v1`

### Tasks

| TASK_ID | Title | Depends on |
|---|---|---|
| TASK_311 | Pass record v0.2 schema fields | none |
| TASK_312 | Pass UNDECIDED emission — FS_COPY dest-exists | TASK_311 |
| TASK_313 | Pass UNDECIDED test coverage | TASK_311, TASK_312 |

### Acceptance criteria (phase-level)

- `policy-eval.py` emits `record_version: "0.2"`, `record_type: "pass_decision"`, and `process_id` on all records
- `policy_decision: "UNDECIDED"` is emitted (not DENY) for FS_COPY when dest exists and overwrite not requested
- `policy_reasons: []` for UNDECIDED records
- `insufficiency` block is present and complete for UNDECIDED records; absent for ALLOW/DENY records
- All existing ALLOW/DENY cases pass without behavioral change
- Gate behavior unchanged: UNDECIDED does not open the gate
- Existing tests pass (backward-compatible)
- New UNDECIDED test coverage passes

### Architecture constraints enforced in Phase 1

- `insufficiency` block must not classify the insufficiency (classification is Triage's job)
- `process_id` generation: `sha256(session_id + ":" + request_id + ":process")[:16 hex chars]`
- `record_version` bumped to "0.2" — additive only; no existing fields removed

---

## Phase 2: Triage Evaluator — COMPLETE (LANDED)

**Gate**: All Phase 1 tasks merged (satisfied).

**Goal**: Implement `triage-eval.py` — a standalone Python script that receives a Pass UNDECIDED record and produces a v0.2 Triage decision record for the FS_COPY dest-exists case.

**Workfront branch (when activated)**: `codex/RDD_TRIAGE_EVAL__v1`

### Landed tasks

| TASK_ID | Scope |
|---|---|
| TASK_320 | `triage-eval.py` emission and chain append |
| TASK_321 | Pass→Triage conditional invocation wiring |
| TASK_322 | Triage evaluator deterministic coverage |

### Phase 2 acceptance criteria

- `triage-eval.py` accepts a v0.2 Pass UNDECIDED record as input
- Produces a v0.2 Triage record with `findings` array, `governing_condition`, `disposition`, `structural_signals`
- F1 (`rule_gap`, `basis: "deterministic"`, `structural_deficiency: true`, no `basis_detail`) is present
- F2 (`insufficient_information`, `basis: "judgmental"`, `basis_detail` non-empty, `structural_deficiency: false`) is present
- `governing_condition: "F1"` with non-empty `governing_rationale`
- `disposition.type: "DEFER_STRUCTURAL_DEFICIENCY"` with `signal_ref` and `structural_change_needed`
- `structural_signals` contains one entry (S1) linked to F1
- Terminal Judgment is not reached
- `originating_pass_hash` matches the input Pass record's `record_hash`
- `process_id` matches the input Pass record's `process_id`
- Triage record is appended to chain; `prev_record_hash` is correct
- Triage record is signed with Ed25519 (same infrastructure as Pass)
- Triage does not emit ALLOW, DENY, or UNDECIDED as disposition type
- Triage does not resolve the case (no rule completion or informal precedent)

### Architecture constraints for Phase 2

- `triage-eval.py` is a standalone script (same pattern as `policy-eval.py`) — not embedded in MCP server
- Invocation: the caller shell script checks `policy_decision == "UNDECIDED"` in Pass output and conditionally invokes triage-eval.py
- Classification criteria for the FS_COPY case are hardcoded in `triage-eval.py`
- F2 `basis_detail` uses a standard template string — no runtime generation of novel judgment

### Phase 2 activation note

Phase 2 activation completed and landed via `TASK_320`–`TASK_322`.

---

## Phase 3: Chain Verification Extension — COMPLETE (LANDED)

**Gate**: All Phase 2 tasks merged (satisfied).

**Goal**: Extend `verify-chain.py` with new rules for multi-record processes.

**Workfront branch (when activated)**: `codex/RDD_CHAIN_VERIFY__v1`

### Landed tasks

| TASK_ID | Scope |
|---|---|
| TASK_323 | Chain verifier multi-record rules |
| TASK_324 | Chain verifier coverage and backward-compat regression |

### Phase 3 acceptance criteria

- `verify-chain.py` validates: records with same `process_id` appear in order `pass_decision` → `triage_decision` → `terminal_judgment`
- `verify-chain.py` rejects: a `triage_decision` whose `originating_pass_hash` references a non-UNDECIDED Pass record
- `verify-chain.py` rejects: a `pass_decision` that contains `originating_triage_hash` or `originating_terminal_hash` for the same `process_id` (one-way flow)
- `verify-chain.py` rejects: out-of-order process records (triage before pass, terminal before triage)
- Existing ALLOW/DENY records (without `record_type`) pass unchanged
- Full end-to-end chain (Pass UNDECIDED → Triage DEFER_STRUCTURAL_DEFICIENCY) passes verification

### Architecture constraints for Phase 3

- Verification failures must be fail-closed — if process ordering cannot be verified, chain fails
- Backward compatibility with v0.1 records is non-negotiable

---

## Phase 4: Minimal Structural Feedback Plumbing — COMPLETE (LANDED)

**Gate**: All Phase 3 tasks merged (satisfied).

**Goal**: Provide a minimal signal extraction mechanism. Structural signals embedded in Triage records must not be lost.

**Workfront branch (when activated)**: `codex/RDD_SIGNAL_EXTRACT__v1`

### Landed tasks

| TASK_ID | Scope |
|---|---|
| TASK_325 | Signal extractor minimal plumbing |
| TASK_326 | Signal extractor deterministic coverage |

### Phase 4 acceptance criteria

- Signal extractor reads Triage records from decision chain
- Produces a flat signal index: `signal_id`, `deficiency_class`, `surface`, `description`, `case_ref` per signal
- Output written to `out/rdd/signal-index.json`
- Extractor is idempotent — running twice produces identical output
- Extractor emits no analysis output — extraction only
- Extractor does not propose structural changes
- Extractor does not modify any system rules, mappings, or criteria

### Architecture constraints for Phase 4

- Output is a passive record — it is not consumed by any automated process in v1
- No analysis, no pattern detection, no proposal generation in Phase 4
- This is the Structural Feedback Function's v1 signal-collection stub only

---

## Phase Activation Protocol

When a phase completes (all tasks Merged):

1. Cecil verifies that all acceptance criteria for the completed phase are satisfied
2. Cecil creates task files for the next phase's proposed tasks, numbered from the current highest TASK_ID
3. Cecil adds the new tasks to `docs/dev/WORK_QUEUE.md` under a new tranche section
4. Task files are placed in `docs/dev/tasks/ready/`
5. Cecil updates this planning document: mark completed phase as COMPLETE, update next phase status to IMPLEMENTATION READY

Current-main note:
- This protocol was exercised through Phase 11 in bounded increments.
- Ready-task inventory includes `TASK_311` through `TASK_340`.
- Next lane should be determined by bounded restock/spec rather than extending this document with speculative future phases.

---

## Must-Have vs Defer (v1 overall)

### Must-have for v1 integrity

- UNDECIDED emitted with structural honesty (Phase 1)
- Triage record with concurrent findings, basis tags, structural signals (Phase 2)
- One-way flow enforced at chain verification layer (Phase 3)
- Structural signal collection (Phase 4)
- Terminal Judgment as schema and chain rule — no runtime (Phase 2–3)
- Fail-closed preserved throughout: UNDECIDED does not open the gate

### High-value but deferred beyond v1

- Triage MCP server inline integration
- Second UNDECIDED case class
- Broader multi-case selector generalization beyond current bounded case class

### Explicitly out of scope for v1

- Terminal Judgment runtime
- Structural Feedback Function analysis
- Multi-domain support
- Formal Triage exhaustion verification
- Domain calibration framework
- Structural Feedback observation scope governance
- Feedback evaluation machinery

---

## Workfront Naming Conventions

| Phase | Workfront branch | Evidence path prefix |
|---|---|---|
| 1 | `codex/RDD_PASS_UNDECIDED__v1` | `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/` |
| 2 | `codex/RDD_TRIAGE_EVAL__v1` | `docs/dev/evidence/RDD_TRIAGE_EVAL__v1/` |
| 3 | `codex/RDD_CHAIN_VERIFY__v1` | `docs/dev/evidence/RDD_CHAIN_VERIFY__v1/` |
| 4 | `codex/RDD_SIGNAL_EXTRACT__v1` | `docs/dev/evidence/RDD_SIGNAL_EXTRACT__v1/` |
