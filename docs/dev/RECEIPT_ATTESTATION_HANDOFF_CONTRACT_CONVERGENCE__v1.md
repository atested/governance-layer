# Receipt Attestation Handoff Contract Convergence v1

## Selected Seam Set
- receipt-attestation export status-contract convergence
- receipt-attestation verify status-contract convergence
- deterministic export -> verify handoff evidence for receipt bundles

## Baseline Already Landed
- receipt attestation export exists and is deterministic
- receipt-bundle verification exists and detects tamper/signature failures
- tool-event and tool-catalog export/verify surfaces already expose narrower machine-readable status contracts

## What Remained Thin
- receipt export did not expose bundle identity and manifest-hash markers comparable to the other bundle exporters
- receipt verify relied on human `PASS:` / `FAIL:` lines only, which is weaker for external handoff automation and bundle-level parity

## Why These Seams Belong Together Now
- They form one externally meaningful handoff object: export a receipt bundle, then verify it with deterministic machine-readable linkage
- They share the same manifest identity and signature/tamper acceptance logic
- They improve external defensibility without widening into validator or release-gate redesign

## Constitutive
- export output markers for receipt bundles
- verify output markers for receipt bundles
- deterministic linkage via bundle id and manifest sha

## Supporting
- broader proof-packet work
- external validator / release-gate work
- CI and docs packaging work

## Explicit Exclusions
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- proof-packet format redesign
- GovMCP runtime or server expansion

## Minimum Closure Logic
1. Receipt export emits deterministic machine-readable contract markers including manifest identity.
2. Receipt verify emits deterministic machine-readable success/failure markers including manifest identity.
3. Human-readable `PASS:` / `FAIL:` verifier output remains intact for existing workflows.
4. Signature-required and tamper-failure paths remain fail-closed.

## Acceptance Proof
- deterministic export contract test across two runs
- deterministic verify contract test across two runs
- negative-path proof for tamper and signature-required failure
- positive export -> verify handoff proof using the same manifest identity markers

## False-Closure Cases
- export adds markers but verify still only exposes human text
- verify adds a machine line but it is not linked to manifest identity
- success-path output improves while tamper or signature-required failures regress
