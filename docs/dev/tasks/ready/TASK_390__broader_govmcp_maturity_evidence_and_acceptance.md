# TASK_390 — Broader GovMCP maturity evidence and acceptance

SPEC_EXPECTED: DOC

## Objective
Produce the bounded analysis/spec task that defines exact evidence, demonstrations, negative cases, and acceptance criteria for claiming the selected broader GovMCP maturity seam is closed.

## Scope
- Use `TASK_388` and `TASK_389` as governing inputs.
- Define exact closure evidence for the selected broader GovMCP maturity seam.
- Define mandatory demonstrations and negative / false-closure cases.
- Distinguish evidence of genuine seam closure from evidence that only proves the already-landed minimum required path or adjacent/supporting health.

## Exclusions
- No implementation work.
- No broad connector redesign.
- No reopening of minimum-path acceptance logic except to preserve the seam boundary.
- No tests.

## Allowlist
- bounded analysis/spec artifacts directly required to define evidence and acceptance for the selected maturity seam

## Acceptance criteria
- The task defines exact closure evidence for the selected broader GovMCP maturity seam.
- The task defines mandatory demonstrations and false-closure cases.
- The task keeps minimum-path closure evidence distinct from broader maturity closure evidence.
- The result is precise enough to govern a later bounded implementation lane.

## Stop rules
- STOP if acceptance criteria cannot be defined honestly from the selected seam and closure plan.
- STOP if the task would blur the selected seam with broad GovMCP maturity or supporting-surface health.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep evidence/acceptance specific to the chosen maturity seam.
- Do not let supporting or adjacent surfaces masquerade as seam closure.
- Do not let the acceptance standard widen into broad GovMCP completion.
