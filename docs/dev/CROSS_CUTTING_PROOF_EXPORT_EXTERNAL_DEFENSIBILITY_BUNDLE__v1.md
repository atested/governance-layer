# Cross-Cutting Proof/Export And External-Defensibility Bundle v1

## Objective
Define the next compound bundle after the current GovMCP tool-catalog slice/query seam merge: a bounded cross-cutting proof/export and external-defensibility hardening bundle.

This artifact is framing only. It is intended to be the next Codex launch point after Cecil merges the current tool-catalog slice/query branch.

## What Is Already Baseline
- GovLayer-core trust-grade closure is landed baseline.
- GovMCP minimum required-path closure is landed baseline.
- GovMCP inspectability/query seam closure is landed baseline.
- GovMCP tool-catalog exposure coherence closure is landed baseline.
- Current branch extends tool-catalog maturity through bounded MCP slice/query/report semantics.

## Why This Bundle Exists
Current main has multiple adjacent proof/export surfaces that are individually meaningful but too coupled to justify separate micro-lanes now.

They share the same external-defensibility objective:
- exported governance artifacts must be deterministic
- exported artifacts must carry aligned machine-readable contracts
- packet/verifier surfaces must reject mismatch and tamper cleanly
- external validation must prove the shipped bundle is coherent

## Adjacent Seams That Belong Together
### 1. Export contract convergence across emitted proof artifacts
Constitutive surfaces:
- `scripts/attest/export_receipt_bundle.py`
- `scripts/attest/export_tool_event_bundle.py`
- `scripts/attest/export_tool_catalog_bundle.py`
- directly related export/verify tests under `system/tests/`

Why this belongs:
- these emit externally consumed artifacts
- they should converge on stable machine-readable status/manifest/report conventions where the contract is constitutive to handoff integrity

### 2. Proof-packet build/verify contract hardening
Constitutive surfaces:
- `scripts/proof-packet.py`
- proof-packet tests under `tests/`
- deterministic verifier summary outputs such as `proof_packet_verify_summary.json`

Why this belongs:
- proof-packet is the cross-cutting package layer that turns exported artifacts into externally reviewable bundles
- packet-manifest correctness and verifier strictness are part of the same external-defensibility chain as export correctness

### 3. External proof-bundle validation and parity hardening
Constitutive surfaces:
- `system/scripts/validate-proof-bundle.sh`
- tests enforcing proof-bundle required files, summary JSON, and parity scans
- external packaging/validator contract tests already present in `tests/` and `system/tests/`

Why this belongs:
- external defensibility is incomplete if exported artifacts and proof packets are deterministic but the shipped bundle validator/parity contract remains thin or inconsistent

## Why These Seams Belong Together Now
- They share files, contract logic, and acceptance logic around deterministic exported evidence.
- They all serve one operator-facing outcome: externally defensible proof handoff, not just local internal correctness.
- Treating them as isolated micro-lanes would increase merge overhead without materially reducing architectural risk.

## Constitutive vs Supporting
### Constitutive
- export command output contracts for receipt/tool-event/tool-catalog proof artifacts
- proof-packet manifest/hash/summary/verifier alignment
- external proof-bundle validator and required-file/summary parity where that parity is necessary to validate shipped outputs

### Supporting
- GitHub Actions upload shape
- release-gate informational integration
- docs-only packaging guidance
- queue/process or DevCore workflow surfaces

Supporting surfaces matter, but they should not be counted as closure of this compound bundle by themselves.

## Explicit Exclusions
- Do not reopen landed GovLayer or GovMCP baselines.
- Do not reopen the current tool-catalog slice/query seam.
- Do not widen into broad `mcp/server.py` or connector redesign.
- Do not treat generic CI or workflow work as substitute closure.
- Do not turn this into a long-range roadmap or broad documentation cleanup.

## Minimum Closure Logic
The compound bundle should be considered materially closed only if all of the following are true:

1. Exported proof artifacts expose aligned deterministic contract markers.
2. Proof-packet build/verify consumes those artifacts without hidden format drift.
3. External validator/parity surfaces can verify the shipped bundle as a coherent external handoff object.
4. Negative-path behavior exists for mismatch, missing artifact, malformed contract, and tamper cases.
5. Closure remains bounded to export/verify/validation surfaces and does not depend on unrelated runtime redesign.

## Evidence That Counts As Bundle Closure
- Determinism proof across two runs for the touched export/packet/validator summaries.
- Positive-path proof that emitted artifacts, proof-packet manifests, and validator summaries align on the same contract versions and hashes.
- Negative/anti-inflation proof for at least:
  - missing required exported artifact
  - hash or linkage mismatch
  - malformed summary/manifest contract
  - tampered packet or bundle payload
- One end-to-end external handoff proof showing:
  - export -> packet -> validate
  - with deterministic outputs and fail-closed verification

## Likely Initial Work Shape
The next launch should prefer one bounded compound bundle with three fronts:
- Front A: export output contract convergence
- Front B: proof-packet/verifier contract hardening
- Front C: external validator/parity hardening for shipped bundle defensibility

## What Should Stay Out Of Scope In The First Launch
- broad GitHub Actions or release-gate redesign
- general docs packaging cleanup
- new GovMCP application seams
- RDD continuation

## Recommended Next Bundle After Current Merge
- `Cross-cutting proof/export and external-defensibility hardening`

## Launch Constraint
Start this bundle only after Cecil merges the current tool-catalog slice/query seam branch, so the current GovMCP continuation work is treated as baseline input rather than parallel moving context.
