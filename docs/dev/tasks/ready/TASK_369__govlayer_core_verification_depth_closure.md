# TASK_369 — GovLayer core verification-depth closure

SPEC_EXPECTED: DOC

## Objective
Produce the bounded implementation-ready closure task for the GovLayer-core verification-depth gaps identified by `TASK_365` and required by `TASK_366`, including canonical verifier ownership, trust-grade verifier guarantees, stronger fail-closed strictness requirements, and invariant/status alignment.

## Scope
- Review the GovLayer boundary, readiness, verification-depth hardening, and trust-claim upgrade artifacts with emphasis on verification closure requirements.
- Define the exact implementation-ready closure scope for GovLayer-core verifier semantics.
- Specify the owned GovLayer verification surfaces and their non-core exclusions.
- Specify the trust-grade verifier guarantees required for the stronger claim.
- Specify the fail-closed strictness and status/invariant alignment work needed before the stronger trust claim becomes honest.

## Exclusions
- No GovMCP-local verification implementation planning beyond explicit dependency-boundary notes.
- No cross-cutting proof/export/packaging validation promotion into core GovLayer verification closure.
- No DevCore workflow/process maturity work except where it must remain visible as adjacent and non-counting.
- No AAT / Foundation v0 ownership resolution unless repo evidence already places a surface cleanly inside GovLayer.

## Allowlist
- `docs/dev/tasks/ready/TASK_369__govlayer_core_verification_depth_closure.md`
- `docs/dev/evidence/TASK_369/**`

## Acceptance criteria
- The task defines the explicit GovLayer-owned verification seam and its non-core exclusions.
- The task defines implementation-ready trust-grade verifier guarantees.
- The task defines the stronger fail-closed strictness requirements needed for the stronger claim.
- The task defines the invariant/status alignment work required for verification-depth closure.
- The task preserves the rule that GovMCP-local checks, DevCore workflow maturity, and cross-cutting packaging/proof validation do not count as GovLayer trust-grade completion.

## Stop rules
- STOP if the task would require counting GovMCP exposure, connector-local checks, or MCP-local stores as GovLayer verification-depth completion.
- STOP if the closure scope cannot be defined without promoting proof/export/packaging validation into core GovLayer completion.
- STOP if unresolved AAT / Foundation v0 surfaces would need to be counted as owned GovLayer depth without new repo-grounded evidence.

## Constraints
- Keep the task centered on GovLayer-core verifier semantics.
- Preserve the mixed-evidence state from `TASK_365` until status/invariant closure is explicitly defined.
- No merge work.
