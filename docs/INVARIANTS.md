# Invariants (v0.2)
Updated: 2026-04-03

## Always-on invariants
INV-001 No privileged action without a decision record.
INV-002 No decision record without a completed policy evaluation.
INV-003 No policy evaluation without tool capability metadata.
INV-004 Logs are append-only and tamper-evident via hash chaining.
INV-005 Trust-grade records are signed; verifier must validate chain + signatures.
INV-006 Any denial must include machine-parsable reason codes.
INV-007 Any redaction must be explicit; never silently drop args/evidence.
INV-008 Replay verifier must reproduce policy outcomes for stored inputs.
INV-009 The evaluate endpoint must never return immediate DENY solely because a tool name is unrecognized. Unknown tools are auto-classified to the nearest governance category and evaluated normally. Classification metadata is attached to the response. Learned mappings are persisted to `capabilities/learned-tool-mappings.json`.

## Optional invariants (later)
INV-101 Rate limits per capability class.
INV-102 Two-person rule for high-risk capabilities.
INV-103 Separation of duties for policy authoring vs deployment.
