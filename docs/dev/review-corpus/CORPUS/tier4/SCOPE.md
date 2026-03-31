# Scope (v0.1)
Updated: 2026-02-15

## What this governance layer IS
1. A non-bypassable chokepoint for privileged actions (tools).
2. A deterministic policy engine that returns allow/deny with reasons.
3. A decision recording and attestation system (signed, tamper-evident logs).
4. A replay/verifier mechanism that can detect tampering and non-compliance.

## What this governance layer is NOT
1. A general "alignment" solution.
2. A replacement for application security, OS sandboxing, or access control.
3. A guarantee against all data exfiltration (only what is within the enforced tool boundary).
4. A promise that LLM outputs are correct—only that process integrity is verifiable.

## Success criteria
1. Every privileged action is preceded by a policy decision and produces a decision record.
2. Logs are append-only and tamper-evident; verifier flags tampering.
3. Bypass attempts are blocked or recorded as policy denials with evidence.
4. The system is client/model-agnostic within a defined integration boundary.
