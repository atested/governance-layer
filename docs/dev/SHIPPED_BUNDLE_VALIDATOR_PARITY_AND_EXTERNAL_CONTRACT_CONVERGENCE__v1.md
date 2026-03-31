# Shipped-Bundle Validator Parity And External-Contract Convergence v1

## Objective
Close the next bounded external-defensibility seam after the landed receipt-attestation and proof-packet handoff milestones: shipped-bundle validator parity and external-contract convergence.

## Selected Seam Set
Work together now:
- proof-packet verifier summary external-contract clarity
- validator summary JSON external-contract clarity
- parity enforcement between published external-contract docs and shipped-bundle machine-readable summary semantics

Do not work now:
- validator implementation redesign
- release-gate redesign
- CI/process integration
- unrelated GovMCP continuation

## What Is Already Baseline
- Receipt-attestation export/verify handoff convergence is landed.
- Proof-packet pack/verify handoff convergence is landed.
- `validate-proof-bundle.sh` already emits deterministic summary JSON.
- `proof-packet.py verify --summary-json` already emits deterministic verifier summary JSON.

## What Remains Thin
- External contract docs still describe the bundle at a higher level than the actual machine-readable summary surfaces now support.
- Packaging smoke and parity evidence do not yet enforce that these published machine-readable summary contracts remain aligned with the actual shipped-bundle semantics.
- Without that parity, GovCore can claim internal contract convergence more strongly than it can claim external consumer-facing contract clarity.

## Why These Seams Belong Together
- They share the same external consumer outcome: a shipped proof bundle whose machine-readable summaries are both documented and parity-checked.
- They use the same files and acceptance logic:
  - `docs/EXTERNAL_CONTRACTS.md`
  - `docs/DISTRIBUTION.md`
  - `scripts/proof-packet.py`
  - `system/scripts/validate-proof-bundle.sh`
  - bounded contract/parity tests
- Treating them separately would split one externally meaningful contract into smaller documentation-only and test-only micro-lanes.

## Constitutive vs Supporting
Constitutive:
- documented machine-readable field set and status semantics for `proof_packet_verify_summary.json`
- documented machine-readable field set and status semantics for `validate_proof_bundle_summary.json`
- parity tests that fail when those published contracts drift from the actual producer/validator behavior

Supporting:
- generic packaging docs not tied to machine-readable semantics
- CI hooks and workflow wiring
- broader release-gate documentation cleanup

## Explicit Exclusions
- Do not edit `system/scripts/validate-proof-bundle.sh`.
- Do not edit `system/scripts/release-gate.sh`.
- Do not claim broader proof/export completion.
- Do not reopen landed GovLayer or GovMCP baselines.

## Minimum Closure Logic
This seam is materially closed only if:
1. `docs/EXTERNAL_CONTRACTS.md` documents the constitutive machine-readable summary contracts that external users actually receive.
2. `docs/DISTRIBUTION.md` reflects the validator summary artifact as a shipped-bundle optional machine-readable output.
3. Bounded parity evidence proves the documented summary contracts remain aligned with actual producer/validator behavior.
4. Closure remains limited to shipped-bundle external contract clarity and parity, not validator implementation redesign.

## Acceptance Proof
- External contract docs explicitly name:
  - `proof_packet_verify_summary_v1`
  - `validate_proof_bundle_summary_v1`
  - the co-located `validate_proof_bundle_summary.json` artifact
- External contract docs describe the constitutive summary fields and status semantics that are already enforced by existing producer/validator tests.
- Packaging smoke passes with the new shipped-bundle machine-summary references.
- A dedicated parity test passes against docs plus actual code/test-backed contract tokens.

## False-Closure Cases
- Adding docs prose without parity enforcement.
- Adding parity tests without updating external-contract docs.
- Treating generic packaging/docs cleanup as closure.
- Claiming validator/parity convergence while machine-readable summary semantics remain undocumented to external consumers.
