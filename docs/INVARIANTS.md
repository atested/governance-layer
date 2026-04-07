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
INV-010 Every writer to `decision-chain.jsonl` must acquire the chain lock protocol before reading the head hash and appending. The protocol is: (1) cross-process `mkdir` lock at `<chain_path>.lock.d`, (2) within that lock, read `prev_record_hash` from the chain tail, compute `record_hash`, and append in a single atomic `O_APPEND` write, (3) in-process threading lock (Python) or shell single-threading guarantees per-process serialization. Python writers use the `_append_chain_record_atomic`-style helper; shell writers (`scripts/append-record*.sh`) implement the mkdir lock directly. Rationale: D-021 — three historical chain breaks on 2026-04-04 were caused by a writer that read the head hash outside the lock. D-024 introduced the atomic read-inside-lock fix. New writers must conform or they re-introduce the race. Conformance verified by audit (see `docs/investigations/D-2026-0407-004-chain-writer-audit.md`).

## Optional invariants (later)
INV-101 Rate limits per capability class.
INV-102 Two-person rule for high-risk capabilities.
INV-103 Separation of duties for policy authoring vs deployment.
