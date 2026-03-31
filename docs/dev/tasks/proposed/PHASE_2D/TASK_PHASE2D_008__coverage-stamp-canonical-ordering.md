# TASK_PHASE2D_008 — Coverage Stamp Canonical Ordering

## Scope
Define canonical ordering rules for coverage stamp serialization and comparison.

Ordering rules:
- Surface ordering: `web, filesystem, shell, routing, model, memory, network, toolchain`
- Object key ordering: lexicographic ascending.
- Array ordering: deterministic only; no runtime insertion order allowed.

Serialization rules:
- JSON emitted compact with trailing newline.
- No pretty-print spacing in canonical form.

Examples:
- PASS: surfaces serialized in canonical order with sorted keys and deterministic digest equality across runs.
- FAIL-CLOSED: any out-of-order `surfaces` list when required ordering is enforced returns nonzero.

## Non-goals
- No runtime serializer implementation.
- No schema version changes beyond ordering constraints.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_008__coverage-stamp-canonical-ordering.md`

## Acceptance criteria
- Surface order is explicit.
- Key/array ordering and serialization constraints are explicit.
- PASS + FAIL-CLOSED examples included.

## STOP conditions
- Stop if canonical ordering depends on non-deterministic runtime enumeration.
- Stop if rules cannot be applied consistently across tools.

## Determinism notes
- Canonical ordering must produce byte-identical output for identical logical input.
- Excluded: non-canonical pretty views used only for debugging.
