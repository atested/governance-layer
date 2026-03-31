# TASK_397 — Broader GovMCP tool-catalog closure plan

SPEC_EXPECTED: DOC

## Objective
Produce the bounded analysis/spec task that defines the minimum changes needed to close the selected broader GovMCP tool-catalog maturity seam without widening into broad connector redesign.

## Scope
- Use `TASK_396` as the governing seam-selection input.
- Define the minimum closure path for the selected tool-catalog seam.
- Distinguish:
  - true seam-closure changes
  - supporting but non-blocking improvements
  - adjacent surfaces that must remain non-constitutive
  - any sensitive surfaces that must stay downstream unless repo evidence proves otherwise
- State whether the seam should close through:
  - store/query contract alignment
  - report/slice consistency
  - export/verify alignment
  - a narrower alternative justified by repo evidence
- Identify the minimum implied implementation fronts.

## Exclusions
- No implementation work.
- No broad connector redesign.
- No broad `mcp/server.py` rewrite.
- No reopening of the minimum required-path or inspectability/query seam baselines.
- No generic GovMCP maturity plan detached from the selected tool-catalog seam.

## Allowlist
- bounded analysis/spec artifacts directly required to define the closure plan for the selected tool-catalog seam

## Acceptance criteria
- The task defines a minimum closure path specific to the selected tool-catalog seam.
- The task remains narrower than broad connector redesign.
- The task keeps already-landed GovMCP baselines intact and out of re-litigation.
- The task distinguishes seam-closure work from supporting or adjacent improvements.
- The output gives `TASK_398` exact closure fronts to evaluate.

## Stop rules
- STOP if the selected tool-catalog seam cannot be converted into an honest bounded closure plan.
- STOP if the plan would require broad `mcp/server.py` or connector redesign by default.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep closure planning narrower than broad GovMCP redesign.
- Treat proof/export and DevCore workflow as supporting unless evidence proves they are required.
- Preserve the already-landed GovMCP minimum-path and inspectability/query baselines.
