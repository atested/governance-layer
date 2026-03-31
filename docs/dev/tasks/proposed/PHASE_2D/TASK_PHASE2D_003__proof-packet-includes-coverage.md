# TASK_PHASE2D_003 — Proof-Packet Includes Coverage

## Scope
Specify how proof-packet manifest/summary carry Coverage Stamp data from Phase 2D contracts.

Contract additions:
- Proof-packet manifest includes `coverage_stamp` object.
- Proof-packet verify summary includes `coverage_stamp_summary` object.

Deterministic serialization requirements:
- Compact JSON with trailing newline.
- Sorted object keys.
- Stable ordering of surfaces by canonical surface order.

Example snippet:
```json
{"coverage_stamp_version":"coverage_stamp_v1","surfaces":[{"surface_id":"filesystem","coverage":{"observation":true,"enforcement":true,"provenance":true}}]}
```

## Non-goals
- No implementation of new fields in this task.
- No change to tar/sha packaging mechanics.

## Allowlist
- `docs/dev/tasks/proposed/PHASE_2D/TASK_PHASE2D_003__proof-packet-includes-coverage.md`

## Acceptance criteria
- Manifest and summary inclusion points are explicit.
- Deterministic serialization requirements are explicit.
- Includes at least one concrete example snippet.

## STOP conditions
- Stop if inclusion requires incompatible schema mutation without versioning.
- Stop if canonical ordering is undefined.

## Determinism notes
- Coverage fields must be byte-stable across repeated generation for identical inputs.
- Excluded: non-contractual auxiliary logs.
