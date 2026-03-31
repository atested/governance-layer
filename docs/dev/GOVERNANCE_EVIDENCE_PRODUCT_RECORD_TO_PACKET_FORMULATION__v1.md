# Governance Evidence Product Formulation: Record-to-Packet Coherence v1

## Objective
Decide whether Record-to-Packet Governance Evidence Coherence is a distinct future workfront above the already-consumed receipt, replay, proof-packet, and verifier-summary artifacts, and if so, package it as a bounded formulation target that avoids replaying consumed work.

## Baseline Summary from Canon Repair
- Repaired canon marks post-traceability governance evidence product work as the current NEXT_WORKFRONT_FORMULATION state.
- Evidence-path coherence is the strongest subcandidate inside that lane, with the current narrower need framed as record-to-packet governance evidence coherence.
- Canonical surfaces now record that proof-packet handoff, validator parity, and receipt/tool-event traceability families are consumed baselines (`CURRENT_MAIN_CAPABILITY_MAP.md`, `POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md`).
- Existing code/tests linking receipts → replay → replay audit → proof packet → verifier summary are already landed and part of those consumed baselines.

## Candidate Workfront Shapes for Record-to-Packet Coherence

### Candidate A — Replay Audit → Proof-Packet Manifest Integrity
- Claim: expose a bounded product lane that explicitly ties the replay audit report and policy record to the proof-packet manifest so operators can validate record-to-packet transitions.
- Evidence cited: `scripts/replay-record.py` already writes deterministic replay audit reports, `scripts/proof-packet.py` already enforces `record_bytes_sha256`, `replay_report_hash`, and `summary_report_version`, and tests such as `tests/test_proof_packet_roundtrip_smoke.sh`, `tests/test_proof_packet_summary_json.sh`, and `tests/test_replay_audit_report.sh` already prove those linkages.
- Distinctness test:
  1. Proof-packet handoff work already proves `replay_report_hash` linkage to the manifest; adding another coherence layer would replicate that seam. → **NOT DISTINCT ENOUGH**
  2. Validator parity work already occupies the proof-packet-to-verifier summary parity perimeter; candidate A would not add new validator-parity semantics. → **NOT DISTINCT ENOUGH**
  3. Receipt/tool-event traceability is orthogonal; candidate A does not depend on any missing receipt traces. → **DISTINCT** but overriding failure due to duplication of proof-packet handoff.

### Candidate B — Verifier Summary → Replay/Proof Packet Explanation Layer
- Claim: provide a bounded workfront that documents and forces deterministic alignment between the verifier summary JSON, the proof-packet manifest, and the replay result so operators can see how evidence is re-used downstream.
- Evidence cited: `tests/test_proof_packet_summary_json.sh` and `tests/test_proof_packet_roundtrip_smoke.sh` already validate the JSON summary and its link to the manifest; `scripts/proof-packet.py` already emits the `verifier_summary` artifact.
- Distinctness test:
  1. Proof-packet handoff already consumes the manifest-to-summary direction; no remaining gap to enforce. → **NOT DISTINCT ENOUGH**
  2. Validator parity coverage already mandates verifier-summary parity; additional work would duplicate parity checks. → **NOT DISTINCT ENOUGH**
  3. Traceability is not implicated; candidate B is about exporter-level summaries. → **DISTINCT** but overall duplication prevents a standalone workfront.

### Candidate C — Replay Report + Verifier Summary Fusion
- Claim: tightly bind replay audit reports with verifier summary metadata so operators can trace evidence from initial policy decision through final proof-packet explanation.
- Evidence cited: `tests/test_replay.sh`, `tests/test_replay_audit_report.sh`, `tests/test_proof_packet_roundtrip_smoke.sh`, and `tests/test_proof_packet_summary_json.sh` already provide deterministic chaining; no code on main leaves that linkage unimplemented.
- Distinctness test:
  1. Proof-packet handoff already covers the replay report ↔ proof-packet handshake; nothing new remains. → **NOT DISTINCT ENOUGH**
  2. Validator parity is again the same coverage surface. → **NOT DISTINCT ENOUGH**
  3. Traceability is peripheral; candidate C would still rely on already-published instrumentation. → **DISTINCT** but replication.

## Comparative Assessment
- **Distinctness**: All three candidates rely on artifacts that are already consumed and enforced by proof-packet handoff or validator parity. None introduce a new artifact whose coherence is currently missing.
- **Strategic value**: While clarity around the evidence path is desirable, forcing a new formulation out of existing linkages would duplicate proofs already present on main and risk turning the lane into documentation/validation duplication.
- **Future boundability**: Without a new pin (e.g., a missing artifact or unresolved coherence requirement), these candidates remain too diffused to bound cleanly.

## Recommendation
**No bounded record-to-packet coherence workfront is currently distinct enough to formulate.** All candidate shapes collapse back into consumed proof-packet handoff or validator parity work when subjected to the fail-closed distinctness tests. The lane remains too diffuse for safe formulation.

### Salvaged tranche truth
The only additive change that landed cleanly is the `governance_evidence` block inside `proof_packet_verify_summary_v1`. Treat this as the bounded proof-packet-only tranche and defer any validator-summary change to a separate workfront.

## Minimum Next Control Step
Monitor for a genuine evidence gap (e.g., missing proof-packet summary metadata, unlinked replay-report hash, or a new post-proof-packet artifact) before re-running a bounded formulation pass. Once a concrete gap surfaces, re-evaluate with the same fail-closed distinctness checklist.

## Evidence That Would Overturn This Conclusion
- A current-main change introducing a new artifact or metric that cannot be mapped to the existing proof-packet handoff parity (e.g., a separate recorded verifier explanation missing from the manifest).
- A formal operator request identifying an unlinked coherence requirement that is not satisfied by the existing tests/code.
- A new canonical artifact (code/tests/docs) showing that a portion of the record-to-packet path is still unverified.
