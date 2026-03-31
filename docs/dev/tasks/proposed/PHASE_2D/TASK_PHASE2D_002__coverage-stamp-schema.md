# TASK_PHASE2D_002 — Coverage Stamp Schema

## Scope
Define the Coverage Stamp schema, placement in emitted outputs, and fail-closed behavior for required stamp checks.

Schema (v1):
- `coverage_stamp_version`: `coverage_stamp_v1`
- `surfaces`: ordered array of surface objects from TASK_PHASE2D_001
- `overall_status`: `complete|partial|missing`
- `generated_by`: tool identifier
- `generated_from`: ordered list of artifact IDs

Placement:
- Include in record payload metadata and verifier summary metadata.

Rule:
- Verified does not imply correctness. Stamp only states what surfaces were covered and how coverage dimensions were populated.

Fail-closed semantics:
- If stamp is required by profile/contract and missing: nonzero failure.
- If stamp present but malformed: nonzero failure.
- If stamp optional and absent: deterministic INFO/SKIP only when explicitly declared by spec.

Canonical ordering:
- `surfaces` array sorted by canonical surface order from TASK_PHASE2D_001.
- Object keys serialized in sorted order.

## Non-goals
- No change to verifier trust model.
- No normative claim that coverage equals policy correctness.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_002__coverage-stamp-schema.md`

## Acceptance criteria
- Schema fields and version are explicit.
- Placement in record + verifier summary is specified.
- Fail-closed semantics are explicit.
- Canonical ordering rules are explicit.

## STOP conditions
- Stop if schema requires breaking existing v1 contracts without version bump.
- Stop if required fields are ambiguous or non-deterministic.

## Determinism notes
- Use stable key ordering and stable surface ordering.
- Explicitly excluded: runtime-specific IDs unless normalized before comparison.
