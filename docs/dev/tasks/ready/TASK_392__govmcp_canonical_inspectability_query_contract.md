# TASK_392 — GovMCP canonical inspectability/query contract

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that defines and lands the canonical inspectability/query contract for the selected receipt-linked GovMCP state, including payload-shape and field expectations, without widening into broad API redesign.

## Scope
- Use `TASK_388`, `TASK_389`, and `TASK_390` as governing inputs.
- Define the authoritative inspectability/query contract for receipt-linked GovMCP state.
- Bound the contract around the receipt-linked state that must agree across:
  - receipt load surfaces
  - replay inspection surfaces
  - receipt-to-tool-event linkage surfaces
  - tool-event-to-receipt linkage surfaces
  - bounded list/recent query surfaces where they are constitutive to the seam
- Identify the narrow implementation center needed to land the contract.

## Exclusions
- No broad `mcp/server.py` rewrite.
- No reopening of the minimum required-path closure claim.
- No tool-catalog expansion by default.
- No bundle/export or proof-surface redesign.
- No tests-only lane design detached from contract closure.

## Allowlist
- bounded implementation surfaces directly required to define and land the canonical inspectability/query contract
- bounded docs/spec/status surfaces directly required to describe the landed contract
- bounded tests directly required to prove the contract if repo norms require them

## Acceptance criteria
- The task defines an explicit canonical inspectability/query contract for the selected receipt-linked state.
- The task identifies the minimum surfaces that must conform to that contract.
- The task stays narrower than broad connector or API redesign.
- The task keeps supporting and adjacent surfaces explicitly non-constitutive unless evidence proves otherwise.
- The result is implementation-ready enough to anchor later consistency alignment.

## Stop rules
- STOP if a canonical contract cannot be defined honestly from current repo behavior.
- STOP if landing the contract would require broad `mcp/server.py` redesign by default.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep the contract bounded to the selected seam.
- Preserve the landed minimum path as already closed baseline.
- Do not let tool-catalog, bundle/export, or DevCore workflow masquerade as contract closure.
