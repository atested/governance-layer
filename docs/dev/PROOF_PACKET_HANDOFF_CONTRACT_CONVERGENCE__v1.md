# Proof Packet Handoff Contract Convergence v1

## Selected Seam Set
- proof-packet pack status-contract convergence
- proof-packet verify status-contract convergence
- deterministic packet -> verifier-summary handoff evidence

## Baseline Already Landed
- proof-packet pack exists and is deterministic
- proof-packet verify exists and catches manifest, hash, size, and linkage failures
- receipt-attestation export/verify handoff contract convergence is landed
- external proof-bundle contracts already treat `proof_packet.tar` and `proof_packet_verify_summary.json` as required external outputs

## What Remained Thin
- `scripts/proof-packet.py` still behaved primarily like an internal utility with ad hoc stdout
- packet identity and manifest identity were not exposed as one aligned machine-readable handoff contract
- verifier summary JSON carried important linkage data, but stdout did not expose a bounded packet-level handoff marker that aligned with that summary

## Why These Seams Belong Together Now
- They form one externally meaningful packet-layer handoff object:
  - build deterministic packet
  - verify deterministic packet
  - produce deterministic verifier summary tied to the same packet identity
- They improve external defensibility without touching forbidden external-validator or release-gate surfaces
- They are more strategic than another local MCP seam because `proof_packet.tar` and `proof_packet_verify_summary.json` are already required external bundle outputs

## Constitutive
- machine-readable pack marker for proof-packet identity
- machine-readable verify marker for proof-packet identity
- deterministic linkage between packet hash, manifest hash, packet id, and verifier summary identity
- additive verifier-summary fields that expose packet identity without breaking `proof_packet_verify_summary_v1`

## Supporting
- external validator parity work
- release-gate integration work
- CI upload or packaging ergonomics
- broad proof/export docs cleanup

## Explicit Exclusions
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- broad proof-packet redesign
- broad external packaging redesign
- GovLayer or GovMCP runtime changes

## Minimum Closure Logic
1. `proof-packet.py pack` emits a deterministic machine-readable status line with packet identity markers.
2. `proof-packet.py verify` emits a deterministic machine-readable status line with the same packet identity markers.
3. When verifier summary JSON is requested, verify output exposes the summary schema marker and summary hash alongside packet identity.
4. Existing human-readable `PASS:` / `FAIL:` behavior remains intact for current workflows.
5. Negative-path verification behavior remains fail-closed.

## Acceptance Proof
- deterministic pack machine-readable contract across two runs
- deterministic verify machine-readable contract across two runs
- positive packet -> verifier-summary handoff proof using the same packet identity markers
- negative-path proof for payload tamper and source-summary linkage mismatch

## False-Closure Cases
- pack exposes packet identity but verify does not
- verify exposes a machine-readable line but it is not linked to the emitted verifier summary
- summary JSON gains additive fields but stdout still cannot expose the bounded packet handoff contract
- positive-path machine markers exist while tamper or linkage mismatch behavior regresses
