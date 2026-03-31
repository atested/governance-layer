# TASK_398 — Broader GovMCP tool-catalog evidence and acceptance

SPEC_EXPECTED: DOC

## Objective
Produce the bounded analysis/spec task that defines exact evidence, demonstrations, negative cases, and acceptance criteria for claiming the selected broader GovMCP tool-catalog seam is closed.

## Scope
- Use `TASK_396` and `TASK_397` as governing inputs.
- Define what evidence counts as closure of the selected tool-catalog seam.
- Require proof that the already-landed GovMCP minimum-path and inspectability/query baselines remain intact while the selected tool-catalog seam improves.
- Define mandatory demonstrations/tests for the selected seam.
- Define false-closure cases that distinguish:
  - selected tool-catalog seam closure
  - generic tool-catalog presence
  - proof/export health
  - broad API cleanup
  - DevCore/process maturity
- Produce an exact acceptance standard for saying the selected broader tool-catalog seam is closed.

## Exclusions
- No implementation work.
- No generic GovMCP maturity acceptance detached from the selected seam.
- No reopening of the minimum required-path or inspectability/query seam baselines.
- No broad connector redesign.
- No broad `mcp/server.py` rewrite.

## Allowlist
- bounded analysis/spec artifacts directly required to define evidence and acceptance for the selected tool-catalog seam

## Acceptance criteria
- The task defines exact seam-specific closure evidence.
- The task requires preservation of the already-landed GovMCP baselines.
- The task defines mandatory demonstrations/tests for the selected seam.
- The task defines explicit false-closure cases.
- The output yields an exact acceptance standard for the selected tool-catalog seam.

## Stop rules
- STOP if honest seam-specific acceptance cannot be defined from repo evidence and the closure plan.
- STOP if the evidence standard would collapse into generic GovMCP maturity or broad connector redesign.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep acceptance tied to the selected tool-catalog seam, not generic GovMCP maturity.
- Do not let proof/export health, DevCore workflow, or already-landed GovMCP baselines masquerade as closure of the selected seam.
