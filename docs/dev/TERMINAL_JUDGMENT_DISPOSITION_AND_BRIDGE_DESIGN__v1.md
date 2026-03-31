# Terminal Judgment Disposition and Bridge Design v1

## Status / Objective
Produce the bounded design specification for the terminal judgment disposition taxonomy, emitter contract, and RDD-to-Gate‑C bridge semantics.

## Problem Statement
Terminal judgment has doctrine-level specification (Level 3 constraints, method types, invariants) but zero runtime implementation, zero defined outcome values, and zero connection to Gate C. Fixtures disagree with schema.

## Bounded Lane Definition
- Disposition taxonomy: ALLOW, DENY, NON_RESOLUTION (ALLOW is the PASS-equivalent).  
- Methods: `human_authority`, `bounded_estimation`, `random_tiebreak`, `non_resolution`.  
- Constraints: `non_resolution` only maps to NON_RESOLUTION; other methods map to ALLOW/DENY.
- Emitter: standalone `terminal-judgment-eval.py`, follows `triage-eval.py`, takes triage record, validates routing, emits signed terminal judgment record with 8 validation rules.
- Bridge: `policy_decision` on terminal judgment mirrors outcome; Gate C consumes it as a normal decision record; no Gate C change needed.

## Key Design Decisions
- Do not broaden to multi-case orchestration or new methods.  
- Bridge is parallel validation (RDD chain and Gate C) so no sequential rewrite.  
- Fixtures normalized to schema.

## In-Scope Surfaces
- Terminal outcome taxonomy, emitter contract, bridge semantics, summary schema prerequisites, fixture normalization requirement.

## Out-of-Scope Surfaces
- Multi-case orchestration, broad doctrine redesign, Gate C modifications, Structural Feedback Function, replay verification of terminal content, new case class definition.

## Acceptance-Proof Concept
Proven when the emitter satisfies the 8 validation rules, chain verification handles 3-record chains, and Gate C accepts the terminal judgment as a decision record (with Category 6 path available).

## Recommended Next Control Steps
Two sequential steps: (1) define the minimal Category 6 case class so terminal judgment is exercisable, (2) implement emitter + fixture normalization + chain verification as a bounded Codex task (fixtures-only testing acceptable if product OK).

## Evidence That Would Overturn
- Existing Category 6 case class on main.  
- Product decides fixtures-only testing is sufficient or defers terminal judgment.  
- Gate C rejects `terminal_judgment` record_type.
