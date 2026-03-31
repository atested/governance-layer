# Roadmap (v0.1)
Updated: 2026-02-15

## Current Position
- Phase 2C.2 is complete.
- Next focus: Phase 2D scoping work (planning only; no implementation start).

## Tracks
1. Governance Layer (primary product)
2. Cecil (harness + test-pilot/engineer)

## Phases and gates

### Phase 0 — Alignment
Deliverables
1. Scope statement (`SCOPE.md`)
2. Threat model (`THREAT-MODEL.md`)
3. Terminology map (in these docs)
Gate
1. One-minute product definition: what it is, isn't, and success criteria.

### Phase 1 — MVG Core (single chokepoint)
Goal
1. Non-bypassable enforcement + auditability for one privileged action class.
Deliverables
1. Intent schema v0.1 (documented in `DECISION-RECORD.md`)
2. Deterministic policy evaluation rules (`POLICY.md`)
3. Decision record format v0.1 (`DECISION-RECORD.md`)
4. Append-only log with hash chaining (implementation + documented semantics)
5. Verifier (tamper detection + replay)
Gate
1. Reproducible decisions for same inputs.
2. Every privileged action produces a signed decision record.
3. Verifier detects log tamper.

### Phase 2 — Adversarial suite + regression discipline
Deliverables
1. Bypass suite v0.1 (`TEST-SUITE.md`)
2. Fuzz dimensions (documented in `TEST-SUITE.md`)
3. Failure taxonomy (`RISKS.md` and/or `TEST-SUITE.md`)
4. One-command regression run producing a report artifact
Gate
1. No known bypass within suite.
2. Failures are reproducible with clear classification.

### Phase 3 — MCP Broker packaging
Deliverables
1. MCP server exposing governed tools only
2. Capability registry
3. Policy config format
4. Telemetry + decision logs
Gate
1. Client cannot reach real tools outside broker.
2. Complete decision artifacts for every invocation.

### Phase 4 — Private pilot
Deliverables
1. 2–5 pilot users, narrow tool surface, default deny
2. Incident response playbook
Gate
1. No catastrophic bypass for defined trial period.

### Phase 5 — OpenClaw candidate integration
Deliverables
1. Adapter/integration
2. Public threat model + guarantees
3. Public verifier tooling or public spec
Gate
1. Independent validation by third parties is practical.
