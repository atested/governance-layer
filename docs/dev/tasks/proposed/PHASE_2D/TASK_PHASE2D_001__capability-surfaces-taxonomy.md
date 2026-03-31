# TASK_PHASE2D_001 — Capability Surfaces Taxonomy

## Scope
Define the canonical capability surface taxonomy for Phase 2D contracts and define coverage dimensions per surface.

Surface list (required):
- web
- filesystem
- shell
- routing
- model
- memory
- network
- toolchain

Per-surface required fields:
- `capability_surface`: stable identifier alias (must equal `surface_id`)
- `surface_id`: stable identifier (from the list above)
- `coverage.observation`: bool
- `coverage.enforcement`: bool
- `coverage.provenance`: bool
- `evidence_sources`: ordered list of source artifacts or checks
- `notes`: optional free text

Coverage meaning:
- Observation: surface behavior can be inspected and reported.
- Enforcement: policy/contract checks actively constrain behavior.
- Provenance: emitted artifacts can prove what checks were executed.

Examples:
- `filesystem`: observation=true, enforcement=true, provenance=true
- `memory`: observation=true, enforcement=false, provenance=false

## Non-goals
- No implementation changes to runtime scripts or verifiers.
- No changes to release-gate behavior.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_001__capability-surfaces-taxonomy.md`

## Acceptance criteria
- Surface list is explicit and complete for this tranche.
- Required per-surface fields are specified.
- Coverage semantics are defined for Observation/Enforcement/Provenance.
- Includes concrete examples.

## STOP conditions
- Stop if taxonomy requires changing hot files.
- Stop if required contract fields cannot be represented deterministically.

## Determinism notes
- Surface IDs and field names are canonical and stable.
- Output ordering must use the declared surface list order unless otherwise specified.
- Explicitly excluded: runtime timestamps and environment-specific path values.
