# TASK_396 — Broader GovMCP tool-catalog seam map

SPEC_EXPECTED: DOC

## Objective
Produce the bounded analysis/spec task that identifies the next sharply bounded GovMCP tool-catalog maturity seam beyond the landed minimum required-path and inspectability/query baselines, including what is already baseline, what remains thin or inconsistent, and what is merely adjacent or supporting.

## Scope
- Use the refreshed canonical planning/status truth as the governing baseline.
- Identify 2 to 4 plausible broader tool-catalog maturity seams from current-main evidence.
- Distinguish for each candidate:
  - what is already baseline
  - what remains thin, inconsistent, adjacent, or under-proven
  - why it is or is not the best next tool-catalog seam
- Separate genuine GovMCP tool-catalog maturity from:
  - already-landed minimum-path behavior
  - already-landed inspectability/query behavior
  - bundle/export or proof-oriented concerns
  - DevCore workflow/process concerns
- Select one sharply bounded tool-catalog seam to govern later planning.

## Exclusions
- No implementation work.
- No broad connector redesign.
- No reopening of the minimum required-path closure claim.
- No reopening of the inspectability/query seam claim.
- No broad `mcp/server.py` rewrite.
- No tests.

## Allowlist
- bounded analysis/spec artifacts directly required to map the next broader GovMCP tool-catalog seam

## Acceptance criteria
- The task defines the landed GovMCP baselines explicitly.
- The task identifies one sharply bounded tool-catalog maturity seam from current-main evidence.
- The task distinguishes core seam surfaces from adjacent or supporting surfaces.
- The task makes clear what remains thin, inconsistent, or out of scope.
- The output gives `TASK_397` and `TASK_398` a bounded seam to plan and evaluate against.

## Stop rules
- STOP if the next tool-catalog seam cannot be identified honestly from repo evidence.
- STOP if the task would force broad connector redesign by assumption.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep the seam map evidence-led and bounded.
- Do not count landed GovMCP baselines as closure of the next tool-catalog seam.
- Do not treat proof/export or DevCore surfaces as constitutive unless evidence requires it.
