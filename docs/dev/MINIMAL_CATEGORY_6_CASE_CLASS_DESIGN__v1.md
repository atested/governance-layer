# Minimal Category 6 Case Class Design v1

## Status / Objective
Produce the bounded design specification for a minimal Category 6 case class that makes terminal judgment exercisable.

## Problem Statement
Terminal judgment (Level 3) is unreachable because the sole v1 case class (FS_COPY dest-exists-no-overwrite) is Category 1 (structural deficiency) and defers at triage. No Category 6 (genuine_residual) case exists on current main.

## Bounded Lane Definition
- Case class: FS_COPY with `intent.constraints.requires_authorization: true`.
- When standard checks pass and destination absent but authorization is required, the evaluator emits `UNDECIDED` because authority is lacking, not rules.
- Triage marks `genuine_residual`, selects `ESCALATION_JUSTIFIED` with method `human_authority`, and routes to terminal judgment.

## Key Design Decisions
- Opt-in path so no existing evaluation changes.
- Single tool (FS_COPY); no multi-tool generalization.
- Deterministic triage classification; no diagnostic judgment.
- Single terminal method `human_authority`; other methods need separate cases.
- No structural signals emitted (correct for Category 6).

## In-Scope Surfaces
- `policy-eval.py` UNDECIDED extension.
- Triage criteria extension.
- Terminal judgment exercisability.
- 3-record chain verification.
- Test fixtures.

## Out-of-Scope Surfaces
- Other tools, authorization patterns, multi-case orchestration, consumed selector work, AAT/proof-export, broad doctrine redesign, other terminal methods.

## Acceptance-Proof Concept
Implementation is provable when the Category 6 path produces a valid 3-record chain (pass → triage → terminal) that passes chain verification and replay integrity checks, satisfying the 11 must-pass and 6 must-not criteria.

## Recommended Next Control Step
SINGLE_BOUNDED_IMPLEMENTATION_TASK combining this design with the terminal judgment design file: implement the Category 6 trigger, terminal judgment emitter, fixture normalization, and test coverage.

## Evidence That Would Overturn
- Product decision to keep terminal judgment schema-only.  
- Conflict with existing `policy-eval` paths.  
- Preference for different Category 6 trigger.  
- Acceptance of fixtures-only testing.
