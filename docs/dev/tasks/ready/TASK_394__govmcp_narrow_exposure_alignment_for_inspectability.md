# TASK_394 — GovMCP narrow exposure alignment for inspectability

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that aligns only the necessary GovMCP exposure/query surfaces to the canonical inspectability/query contract after `TASK_392` and `TASK_393`, without broad `mcp/server.py` rewrite.

## Scope
- Use `TASK_392` and `TASK_393` as governing inputs.
- Identify the minimum exposure-layer/query surfaces that must reflect the canonical inspectability/query contract.
- Align only the seam-relevant downstream surfaces needed to present the already-closed contract and consistency work.
- Keep acceptance tied to the anti-inflation rules from `TASK_390`.

## Exclusions
- No broad `mcp/server.py` rewrite.
- No broad endpoint normalization unrelated to the selected seam.
- No reopening of the minimum required-path closure claim.
- No tool-catalog or bundle/export maturity expansion by default.
- No broad GovMCP usability redesign.

## Allowlist
- bounded implementation surfaces directly required to align seam-relevant exposure/query methods
- bounded docs/spec/status surfaces directly required to describe the aligned exposure behavior
- bounded tests directly required to prove narrow exposure conformance and anti-inflation boundaries

## Acceptance criteria
- The task aligns only the necessary exposure/query surfaces to the canonical inspectability/query contract.
- The task stays downstream of `TASK_392` and `TASK_393` rather than substituting for them.
- The task avoids broad `mcp/server.py` rewrite.
- The result is precise enough to satisfy the seam-specific acceptance standard without inflating the claim.

## Stop rules
- STOP if exposure alignment would require broad server rewrite by default.
- STOP if the task would blur narrow seam closure with generic GovMCP maturity or API cleanup.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep exposure work seam-specific and downstream.
- Do not let broader API cleanup, tool-catalog health, bundle/export health, or DevCore workflow count as closure.
- Preserve the landed minimum path as baseline input and preserve its continuity explicitly.
