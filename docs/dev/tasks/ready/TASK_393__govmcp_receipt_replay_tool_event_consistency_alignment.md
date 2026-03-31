# TASK_393 — GovMCP receipt/replay/tool-event consistency alignment

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready task that aligns receipt, replay, and tool-event linkage surfaces to the canonical inspectability/query contract while preserving the already-landed minimum path.

## Scope
- Use `TASK_392` as the governing contract authority.
- Align receipt, replay, and tool-event linkage semantics to the canonical inspectability/query contract.
- Preserve and explicitly re-prove:
  - deterministic receipt retrieval
  - replay linkage from stored receipt
  - receipt-to-tool-event continuity
- Distinguish:
  - true seam-closure consistency work
  - supporting but non-blocking cleanup
  - adjacent surfaces that remain non-constitutive

## Exclusions
- No broad `mcp/server.py` rewrite.
- No reopening of storage-contract closure or minimum-path acceptance as open blockers.
- No tool-catalog maturity expansion unless implementation evidence later proves it necessary.
- No bundle/export or proof-surface expansion by default.
- No broad GovMCP maturity cleanup.

## Allowlist
- bounded implementation surfaces directly required to align receipt/replay/tool-event linkage behavior to the canonical contract
- bounded docs/spec/status surfaces directly required to describe the aligned behavior
- bounded tests directly required to prove consistency alignment and minimum-path preservation

## Acceptance criteria
- The task materially aligns receipt, replay, and tool-event linkage surfaces to the canonical contract.
- The task explicitly preserves the already-landed minimum path.
- The task distinguishes constitutive seam closure from supporting or adjacent cleanup.
- The result is bounded enough to support later narrow exposure alignment.

## Stop rules
- STOP if consistency alignment cannot be achieved without broad connector redesign.
- STOP if minimum-path preservation would be weakened or blurred by the task.
- STOP if required changes would touch non-allowlisted files.

## Constraints
- Keep the work centered on receipt/replay/tool-event consistency, not generic API polish.
- Preserve GovLayer-core trust-grade behavior as baseline input, not part of the seam.
- Keep supporting surfaces non-constitutive unless evidence proves otherwise.
