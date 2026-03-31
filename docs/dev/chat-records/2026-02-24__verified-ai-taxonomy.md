# Chat Record: Verified AI Taxonomy

**Date**: 2026-02-24
**Context**: User provided DOC-READY SOURCE PACKET developing a general category for AI systems that can be justifiably trusted without requiring people to "trust the model." The chat evolved from a maturity ladder concept into a component taxonomy with three orthogonal pillars.

**Why This Chat Mattered**: As AI outputs become more non-intuitive, humans lose the ability to validate by plausibility. Trust must shift from "does this sound right?" to "was this produced under constraints I accept, with evidence I can audit?" The chat developed a taxonomy to distinguish governance theater from real verification, enabling justifiable trust based on operational admissibility and defensibility.

---

## Structured Record

### Core Concept

**Verified AI**: AI whose outputs are admissible because the system around the model enforces constraints, records what happened, and can prove the record hasn't been tampered with.

**Key framing**: Trust the proof, not the model. Governance systems add overhead, but that overhead can be an **enabling cost** that unlocks safer autonomy, similar to how more compute enabled more robust software stacks.

**Canonical phrase from chat**: *"Verified ≠ correct"* - Governance can't stop internal "thoughts," only actions. The value is operational admissibility and defensibility, not truth certification.

### Evolution: Ladder → Component Taxonomy

Initial concept was a maturity ladder (L0 → L4), but this mixed dimensions (logging quality + enforcement strength + integrity binding). The chat converged on a **component taxonomy** with three orthogonal pillars applied **per capability surface**:

1. **Observation (O)**: "What happened?" - Logging quality and completeness (O0–O3)
2. **Enforcement (E)**: "What cannot happen?" - Gating and bypass resistance (E0–E3)
3. **Provenance/Integrity (P)**: "Can we prove the record and bind artifacts?" (P0–P3)

**Per-Surface Application**: Ratings apply to specific surfaces (filesystem, shell, web, routing, reasoning), not one global label.

**Coverage Stamp Required**: Outputs must declare per-surface ratings to prevent hiding weak surfaces behind strong ones.

**Example**: `FS O3 E2 P2 | Web O2 E1 P1 | Reasoning O1 E0 P0`

### Verified AI Gates (Thresholds)

**Minimal**: O2 + E1 + P1 (structured logging, policy gating, linked artifacts)
**Strong**: O3 + E2 + P2 (complete durable logging, bypass-resistant enforcement, hash-chained integrity)
**Institutional**: O3 + E3 + P3 (add cross-tool invariants, key custody, independent verification)

### Observation Levels (O0–O3)

**O0**: No logging or only sampling
**O1**: Unstructured logs (stdout/stderr, no correlation)
**O2**: Structured event logs with correlation IDs, includes denials and failures
**O3**: Complete durable logging with:
- **"Event before result"**: Event durably stored before returning tool result
- **Crash-resistant completeness mechanism**: Persistent sequence numbers, signed heartbeats, or merkleized streams
- **LOGGING_FAILURE handling**: Structured event or fail-closed behavior when logging durability cannot be confirmed
- **Required logging**: Denials, failures, break-glass events

**O3 tightening (v0.3)**: Must detect outages/gaps. If logging fails, system must emit LOGGING_FAILURE or halt.

### Enforcement Levels (E0–E3)

**E0**: No enforcement (post-hoc detection only)
**E1**: Policy decision before execution, structured denials
**E2**: Non-bypassable or break-glass with detection
- **Break-glass requirement**: Must emit tamper-evident BREAK_GLASS event, mark session UNGOVERNED, propagate marking downstream
**E3**: Deterministic cross-tool invariants across sequences (e.g., merge gate that checks inventory + ops canonical before accepting code merge)

**E2 clarification (v0.3)**: "Non-bypassable" means direct tool access paths are removed or detection-poisoned. Break-glass must be explicit, logged, and propagate UNGOVERNED marker.

**E3 scope (v0.3)**: Narrowly defined as cross-tool invariants, not "govern all planning."

### Provenance/Integrity Levels (P0–P3)

**P0**: No artifact binding or integrity mechanism
**P1**: Artifacts linked and resolvable (must be retrievable or existence-provable at output time)
**P2**: Hash-chained records with:
- **Hashed artifacts** (content addressing or digests in log)
- **Signed checkpoints** (periodic attestations)
- **Machine-readable Integrity Boundary** (enumerates writers, storage, crypto, anchoring, completeness mechanism, threat model in/out of scope)
**P3**: Key custody, rotation/revocation, independent verification without private keys

**P1 strengthening (v0.3)**: "Linked and resolvable" means artifacts must be retrievable or existence-provable, not just referenced.

**P2 Integrity Boundary requirement (v0.3)**: Must enumerate:
- Writers (who/what can append)
- Storage (where logs live, durability guarantees)
- Crypto (algorithms, key IDs)
- Anchoring (external checkpoints if used)
- Completeness mechanism (sequence numbers, heartbeats, merkle streams)
- Threat model (what's in scope vs out of scope)

**Redaction constraints (v0.3)**: Integrity must remain verifiable after redaction (redact-before-hash, Merkle leaf hashing, or dual-log linkage).

### Break-Glass and UNGOVERNED Propagation

**Break-glass**: Explicit override path that bypasses enforcement.

**Requirements**:
- Must emit tamper-evident BREAK_GLASS event
- Must mark session/run as UNGOVERNED
- UNGOVERNED marker must propagate downstream to derived artifacts

**Rationale**: Human operators need escape hatches, but the escape must be auditable and outputs must carry warning labels.

### Claim Verification (CV) Overlay (Optional)

**Separated from core taxonomy**: Verified AI focuses on operational verification. CV levels address epistemic claim substantiation.

**CV0**: Claims without grounding
**CV1**: Claims cite sources (human or tool)
**CV2**: Claims cite verified sources (checksummed, timestamped)
**CV3**: Claims include competing hypotheses and uncertainty

**Status**: Optional. CV may become mandatory for certain high-stakes surfaces/domains in future.

### Minimum Tests Required (v0.3)

To claim higher levels, minimum tests required:

**O3 tests**:
- Outage/gap detection (system detects when logging fails)
- LOGGING_FAILURE event emitted or fail-closed behavior triggered

**E2 tests**:
- Bypass detection (attempt to skip policy gate, verify BREAK_GLASS or UNGOVERNED emitted)
- Break-glass propagation (verify UNGOVERNED marker propagates downstream)

**P2 tests**:
- Tamper detection (modify record, verify hash chain breaks)
- Integrity Boundary machine-readable (parse and validate enumerated components)

### External Evaluation Gaming Risks

The chat included external evaluation that identified gaming risks:

1. **Selective logging**: Only successes logged, not failures → disqualifying unless detectable
2. **Hallucinated artifacts**: Models fabricate provenance not backed by tool reality ("receipt theater")
3. **Weak integrity boundaries**: Vague threat models, missing enumeration
4. **Silent overrides**: Break-glass without propagation or logging

**Mitigation**: v0.3 hardening tightens definitions and adds minimum tests to detect gaming.

---

## Explicit Claims Made in Chat

**Decisions/Commitments**:
- **[DECISION]**: "Adopt 'Verified AI' as the preferred label and use a taxonomy rather than a single maturity ladder."
- **[DECISION]**: "Use a component taxonomy with three pillars: Observation, Enforcement, Provenance/Integrity."
- **[DECISION]**: "Apply ratings per surface and require coverage stamps for outputs/runs."
- **[DECISION]**: "Explicitly state 'Verified ≠ correct' (operational/evidentiary verification, not truth certification)."
- **[DECISION]**: "Harden taxonomy to v0.3 with tightened definitions and minimum tests."
- **[DECISION]**: "Treat integration into project docs as a significant change best handled as documentation v3."
- **[DECISION]**: "Prefer Cecil to incorporate this into repo design documentation when available, with an informational handoff packet."

**Speculative Ideas**:
- **[SPECULATION]**: "Governance overhead will increasingly be 'paid for' by future compute headroom similarly to how RAM/CPU enabled new software stacks."
- **[SPECULATION]**: "Industry infrastructure investment pattern 'we know we'll need it, not sure precisely why' maps to governance verification needs."

**Open Questions**:
- **[OPEN_QUESTION]**: "Exact current surface scores for the governance layer depend on whether denials/failures and post-results are fully captured in logs."
- **[OPEN_QUESTION]**: "How strong integrity boundaries should be to satisfy 'Institutional' expectations under real adversarial assumptions."
- **[OPEN_QUESTION]**: "Whether CV should remain optional or become mandatory for certain high-stakes surfaces/domains."

---

## Key Quotes from Chat

> "Verified ≠ correct." (Operational/evidentiary verification, not truth certification)

> "Trust the proof, not the model."

> "Governance overhead as an enabling cost that unlocks safer autonomy."

> "Event before result." (O3 requirement for durable logging)

> "Break glass is poisonous." (Must emit BREAK_GLASS event and mark session UNGOVERNED)

> "Can't stop the thoughts, just the actions." (Governance focused on tool use, not internal reasoning)

> "Selective logging is disqualifying unless detectable."

> "Integrity Boundary must enumerate writers, storage, crypto, anchoring, completeness mechanism, and threat model."

> "As AI outputs become more non-intuitive, trust must shift from 'does this sound right?' to 'was this produced under constraints I accept, with evidence I can audit?'"

> "Admissibility: outputs accepted because process meets constraints and produces auditable warrants, not because output 'sounds right.'"

---

## Taxonomy Summary (v0.3)

### Observation (O0–O3)

| Level | Definition | Requirements |
|---|---|---|
| O0 | No logging or sampling only | - |
| O1 | Unstructured logs | stdout/stderr, no correlation |
| O2 | Structured event logs | Correlation IDs, denials/failures logged |
| O3 | Complete durable logging | Event before result, completeness mechanism, LOGGING_FAILURE handling |

### Enforcement (E0–E3)

| Level | Definition | Requirements |
|---|---|---|
| E0 | No enforcement | Post-hoc detection only |
| E1 | Policy gating | Decision before execution, structured denials |
| E2 | Bypass-resistant | Non-bypassable or break-glass with UNGOVERNED propagation |
| E3 | Cross-tool invariants | Deterministic checks across sequences |

### Provenance/Integrity (P0–P3)

| Level | Definition | Requirements |
|---|---|---|
| P0 | No artifact binding | - |
| P1 | Linked and resolvable | Artifacts retrievable or existence-provable |
| P2 | Hash-chained integrity | Hashed artifacts, signed checkpoints, Integrity Boundary |
| P3 | Key custody + verification | Rotation/revocation, independent verification |

### Coverage Stamp Format

```
FS O3 E2 P2 | Shell O2 E1 P1 | Web O2 E1 P0 | Reasoning O1 E0 P0
```

### Verified AI Gates

| Gate | Threshold | Use Case |
|---|---|---|
| Minimal | O2 + E1 + P1 | Basic operational auditability |
| Strong | O3 + E2 + P2 | Institutional admissibility |
| Institutional | O3 + E3 + P3 | High-stakes adversarial environments |

---

## Future Discussion Hooks (From Chat)

1. Which surfaces should target Verified Strong vs remain lower with honest coverage stamps, and why?
2. What is the minimum "Integrity Boundary" strength acceptable for institutional buyers versus internal use?
3. How should UNGOVERNED propagation work across chained workflows and derived artifacts?
4. What completeness mechanism is best for O3 in your environment: persistent sequence, signed heartbeats, or merkleized streams?
5. What are the minimal "cross-tool invariants" that justify E3 without creating planning overhead?
6. How should web fetching be governed if replay is impossible: artifact snapshots, content addressing, or "observed only"?
7. Should CV be mandatory for certain domains/surfaces, and what is the threshold for CV2 or CV3?
8. What evidence pack format should accompany a claimed surface rating so claims aren't self-certified?
9. What is the break-glass governance policy for human operators, and how should it be audited?
10. How do you prevent "receipt theater" where models fabricate provenance not backed by tool reality?
11. What retention/redaction model preserves integrity while meeting privacy constraints?
12. What should "Institutional" mean under your stated threat model, and what is out-of-scope?

---

## Example Applications

- **Classifying AI systems** beyond "responsible AI" marketing by separating logging, enforcement, and integrity
- **Institutional-grade justification** for relying on AI outputs when results are non-intuitive
- **Per-surface governance reporting** via coverage stamps (web vs filesystem vs shell vs reasoning)
- **Operational control framing**: "can't stop thoughts, only actions" - governance focused on tool use and auditable records
- **Documentation integration**: Positioning Verified AI taxonomy as design/spec addition for future implementation
- **Public communication**: Short explanations of "log it, block it, prove it" and "thoughts vs actions"
