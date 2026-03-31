# TASK_378 — GovMCP exposure-layer alignment

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that aligns the MCP exposure layer to the canonical storage and continuity contract after `TASK_376` and `TASK_377`, without widening into a broad `mcp/server.py` rewrite.

## Scope
- Use the storage-contract and receipt-continuity results as governing authorities.
- Align the MCP-facing exposure surfaces to the canonical contract only where required for the minimum blocker path.
- Ensure exposure-layer behavior matches the acceptance proof required for blocker closure.
- Keep the work bounded to required-path alignment rather than broad MCP architecture change.

## Exclusions
- No broad `mcp/server.py` redesign.
- No broad MCP feature expansion.
- No GovLayer-core trust-grade work.
- No DevCore workflow/process redesign.
- No supporting-surface cleanup unless directly required to satisfy the acceptance standard.

## Allowlist
- `mcp/server.py`
- minimal adjacent GovMCP exposure surfaces directly required to align the required path
- bounded supporting docs/tests directly required to validate exposure-layer alignment against the acceptance contract

## Acceptance criteria
- The MCP exposure layer matches the canonical storage and continuity contract established by the earlier tasks.
- Changes are bounded to the minimum required-path alignment surface.
- The result aligns exactly to the blocker-closure evidence and false-closure rules established for the lane.
- No broad connector rewrite is introduced.
- GovLayer-core and DevCore contamination remains explicitly avoided.

## Stop rules
- STOP if exposure-layer alignment would require broad server rewrite rather than bounded required-path changes.
- STOP if the task would attempt to satisfy closure through server startup or endpoint response alone.
- STOP if the task would need to count GovLayer-core baseline health or DevCore maturity as constitutive proof.

## Constraints
- Keep the task downstream of storage-contract closure and receipt-to-tool-event continuity closure.
- Use the exact blocker-closure evidence standard for success.
- Do not widen into supporting helper or non-required-path MCP method cleanup.

