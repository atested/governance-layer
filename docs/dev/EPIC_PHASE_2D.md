# EPIC — Phase 2D (Scoping + Contracts)

## Current framing
Phase 2D is a scoping-and-contract tranche. It defines capability surface taxonomy, coverage semantics, stamp schema, and deterministic verification/output contracts.

## Spec Index
- `TASK_PHASE2D_001__capability-surfaces-taxonomy.md` — Canonical capability surface taxonomy and coverage dimensions.
- `TASK_PHASE2D_002__coverage-stamp-schema.md` — `coverage_stamp_v1` schema, placement, and fail-closed semantics.
- `TASK_PHASE2D_003__proof-packet-includes-coverage.md` — Proof-packet manifest/summary coverage inclusion contract.
- `TASK_PHASE2D_004__verify-record-coverage-output.md` — verify-record coverage output format and reason-code contract.
- `TASK_PHASE2D_005__tests-for-coverage-stamp-determinism.md` — Determinism/fail-closed test specification set.
- `TASK_PHASE2D_006__phase2d-epic-scope-refresh.md` — Epic scope framing and tranche boundary refresh.
- `TASK_PHASE2D_007__coverage-stamp-reason-codes.md` — Coverage reason-code taxonomy and terminal code rules.
- `TASK_PHASE2D_008__coverage-stamp-canonical-ordering.md` — Canonical ordering and stable serialization rules.
- `TASK_PHASE2D_009__coverage-stamp-in-policy-eval.md` — policy-eval coverage stamp validation and output contract.
- `TASK_PHASE2D_010__coverage-stamp-in-verify-chain.md` — verify-chain per-record and aggregate coverage contract.
- `TASK_PHASE2D_011__coverage-stamp-in-replay.md` — replay coverage stamp preservation/reporting contract.
- `TASK_PHASE2D_012__coverage-stamp-test-plan-v1.md` — v1 executable-grade coverage test plan contract.

## In-scope for this tranche
- Capability surface taxonomy and coverage dimensions
- Coverage Stamp schema and placement contracts
- Proof-packet coverage inclusion contracts
- verify-record coverage output formatting and reason-code contracts
- Determinism and fail-closed test-plan specifications

## Out of scope for this tranche
- Runtime implementation of Phase 2D contracts
- release-gate behavior changes
- Queue/assignment process changes

## Next tranche boundary
After this scoping pack is accepted, the next tranche is implementation planning and execution against the declared contracts, with deterministic tests and verifier updates performed in follow-on task branches.

## Boundaries
- Phase 2D in this tranche is scoping/contracts/tests planning only.
- No implementation changes are in scope for this tranche.
- Runtime, verifier, and release-gate behavior changes are explicitly deferred to follow-on implementation task branches.

## Alignment note
This epic is intentionally scoped as contract-definition work only, consistent with ROADMAP language of planning/scoping before implementation starts.

<!-- UNION-RESOLUTION: appended cherry-pick variant -->

# EPIC_PHASE_2D

## Selected Target
FS_DELETE (single target)

## Rationale
FS_DELETE has clear fail-closed boundaries, direct operator impact, and deterministic policy/test surfaces.

## Scope
- Recursive-delete policy constraints and intent binding
- Allowlist/root checks for delete targets
- Deterministic DENY reason-code emission for invalid delete intents

## Non-scope
- FS_MOVE cross-root promotion workflow
- Network/egress controls
- Runtime execution sandbox changes

## Capability Additions Needed
- `FS_DELETE.recursive_allowed` policy field enforcement
- Explicit delete-target root validation against allow base dirs

## Policy-Eval Deltas
- Add/confirm checks for recursive disallow paths
- Add/confirm checks for non-file/non-directory delete targets
- Maintain deterministic reason-code ordering for multi-failure cases

## MCP Tool Surface Deltas
- No new MCP tools in Phase 2D scope
- Existing delete flows must preserve intent field requirements

## Tests to Add (IDs / scenarios)
- T-DELETE-RC-001: recursive=true with recursive_allowed=false => DENY + RC-FS-RECURSIVE-DISALLOWED
- T-DELETE-RC-002: target outside allowed roots => DENY + RC-FS-PATH-NOT-ALLOWED
- T-DELETE-RC-003: missing intent fields => DENY + RC-FS-MISSING-INTENT-FIELDS

## Invariants Impacted
- INV-001 fail-closed default DENY
- INV-002 deterministic policy normalization
- INV-004 bounded filesystem scope
- INV-007 deterministic replay/verification compatibility

## Threat Delta
- Reduces accidental destructive actions via explicit recursive and root-bound checks
- Preserves traceability of delete intent failures through deterministic RC outputs

## Fail-Closed Boundaries
- Any malformed delete intent => DENY with deterministic RC
- Any root/path policy mismatch => DENY
- No implicit widening of delete scope from runtime inputs
