# Invariants (v0.1)
Updated: 2026-03-16

## Always-on invariants
INV-001 No privileged action without a decision record.
INV-002 No decision record without a completed policy evaluation.
INV-003 No policy evaluation without tool capability metadata.
INV-004 Logs are append-only and tamper-evident via hash chaining.
INV-005 Trust-grade records are signed; verifier must validate chain + signatures.
INV-006 Any denial must include machine-parsable reason codes.
INV-007 Any redaction must be explicit; never silently drop args/evidence.
INV-008 Replay verifier must reproduce policy outcomes for stored inputs.

## Optional invariants (later)
INV-101 Rate limits per capability class.
INV-102 Two-person rule for high-risk capabilities.
INV-103 Separation of duties for policy authoring vs deployment.
