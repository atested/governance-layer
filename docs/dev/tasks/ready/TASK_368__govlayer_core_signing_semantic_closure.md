# TASK_368 — GovLayer core signing semantic closure

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready closure task for the GovLayer-core signing semantics required by `TASK_364` and `TASK_366`, including explicit GovLayer ownership, trust-grade signed-record emission semantics, mixed signed/unsigned ambiguity closure, and authoritative status/invariant alignment.

## Scope
- Review the GovLayer boundary, readiness, signing hardening, and trust-claim upgrade artifacts with emphasis on signing closure requirements.
- Define the exact implementation-ready closure scope for GovLayer-core signing semantics.
- Specify the ownership boundary between GovLayer record-signing semantics and MCP-local receipt signing.
- Specify the trust-grade signed-record emission requirements and the claim-level treatment of unsigned records.
- Specify the status/invariant alignment work needed before the stronger trust claim becomes honest.

## Exclusions
- No GovMCP-local receipt signing implementation planning beyond seam clarification needed to protect GovLayer ownership.
- No connector/server implementation work.
- No proof/export/packaging promotion into core GovLayer signing completion.
- No verification-depth lane duplication except where signer-side closure depends on explicit verifier-side conditions.

## Allowlist
- `docs/dev/tasks/ready/TASK_368__govlayer_core_signing_semantic_closure.md`
- `docs/dev/evidence/TASK_368/**`

## Acceptance criteria
- The task defines the explicit GovLayer-owned signing seam and its non-core exclusions.
- The task defines implementation-ready trust-grade signed-record emission requirements.
- The task defines how mixed signed/unsigned ambiguity must be closed for the stronger claim.
- The task defines the authoritative status/invariant alignment work required for signing closure.
- The task preserves the rule that GovMCP-local receipt signing does not count as GovLayer trust-grade completion.

## Stop rules
- STOP if the task would require counting MCP-local receipt signing or connector wrappers as GovLayer core completion.
- STOP if the closure scope cannot be defined without widening into GovMCP implementation.
- STOP if the task would silently use proof/export/packaging signing surfaces as proof of core signing closure.

## Constraints
- Keep the task centered on GovLayer-core record-signing semantics.
- Preserve the mixed-evidence state from `TASK_364` until status/invariant closure is explicitly defined.
- No merge work.
