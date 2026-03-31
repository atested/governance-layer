# TASK_389 — Broader GovMCP maturity closure plan

SPEC_EXPECTED: DOC

## Objective
Produce the bounded analysis/spec task that defines the minimum changes needed to close the selected broader GovMCP maturity seam without widening into broad connector redesign.

## Scope
- Use `TASK_388` as the governing seam authority.
- Translate the selected maturity seam into a bounded closure plan.
- Distinguish:
  - true blocker or maturity-fix changes
  - supporting but non-blocking cleanup
  - adjacent GovLayer dependencies
  - adjacent DevCore dependencies
- State the shortest credible path to closing the chosen seam.

## Exclusions
- No implementation work.
- No broad `mcp/server.py` rewrite.
- No reopening of the minimum required-path closure proof.
- No broad GovMCP roadmap design.
- No tests.

## Allowlist
- bounded analysis/spec artifacts directly required to produce the maturity-seam closure plan

## Acceptance criteria
- The task defines the minimum changes required to close the selected broader GovMCP maturity seam.
- The task stays bounded and excludes broad connector redesign.
- The task distinguishes true maturity closure from supporting or adjacent cleanup.
- The result is implementation-ready enough to support a later bounded execution lane.

## Stop rules
- STOP if the selected seam cannot be turned into a bounded closure plan honestly.
- STOP if closure planning would require broad architecture redesign by default.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep the closure plan narrower than broad GovMCP rewrite.
- Preserve the landed minimum-path baseline as already closed.
- Preserve GovLayer/GovMCP/DevCore boundaries explicitly.
