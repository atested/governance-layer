# TASK_412B — Messaging follow-on tranche decomposition v1

## 1. PURPOSE

Decompose current-main messaging follow-on into bounded candidate slices, rank them by dispatch safety and governance leverage, and identify the first safe slice for future dispatch without reopening the first two landed messaging slices.

## 2. CURRENT_MAIN_MESSAGING_SCOPE

- Current main has the bounded messaging proof surface baseline plus two landed slices:
  - `TASK_399`
  - `TASK_400`
- Current-main docs consistently say follow-on remains live but unbounded:
  - `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
  - `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`
  - `docs/dev/DESIGN_TO_REPO_GAP_AUDIT__v1.md`
- Strong messaging design corpus already exists:
  - `docs/dev/MESSAGING_PROOF_SURFACE_IMPLEMENTATION_DESIGN__v1.md`
  - `docs/dev/MESSAGING_CAPABILITY_REGISTRY_AND_MAPPING_SCHEMA__v1.md`
  - `docs/dev/MESSAGING_INVOCATION_SCHEMA__v1.md`
  - `docs/dev/MESSAGING_DECISION_RECORD_EXTENSION__v1.md`
  - `docs/dev/MESSAGING_REASON_CODES__v1.md`
  - `docs/dev/MESSAGING_CONFORMANCE_TEST_DESIGN__v1.md`
  - `docs/dev/MESSAGING_PROXY_LIFECYCLE__v1.md`

## 3. CANDIDATE_SLICES

### Slice A — bounded provider-evidence / receipt-linkage strengthening
- Build on already-landed forwarding receipts and replay-strengthening semantics.
- Narrow objective: strengthen operator-visible proof of delivery / forwarding linkage without widening evaluator-visible content semantics.

### Slice B — structural rate-governance strengthening
- Extend bounded structural rate metadata beyond the current `audit_scope.rate_window_count` reason-code usage.
- Keep this structural and governance-visible, not a full global metering subsystem.

### Slice C — message follow-on contract clarification for post-ALLOW evidence
- Narrow documentation/spec lane that formalizes how post-ALLOW messaging receipts prove stronger replay binding and packet-facing evidence shape.
- Useful but lower leverage than direct bounded execution-facing strengthening.

### Slice D — messaging triage / non-resolution extension
- Introduce non-ALLOW/DENY handling for messaging.
- Current-main evidence repeatedly marks this as absent, but it is materially wider because the existing proof surface is explicitly ALLOW/DENY-only.

## 4. RANKING_LOGIC

1. Prefer slices already implied by landed messaging artifacts and tests.
2. Prefer additive proof/evidence strengthening over changes that alter the baseline decision model.
3. Penalize slices that require broad new infrastructure:
   - global rate metering
   - generic proxy expansion
   - DLP/content moderation
   - messaging triage/non-resolution redesign
4. Prefer slices that stay within the existing messaging proof-surface boundary and can be expressed as one bounded next dispatch.

## 5. FIRST_SAFE_SLICE

**Selected first safe slice:** `Slice A — bounded provider-evidence / receipt-linkage strengthening`

Why it is first:
- strongest overlap with already-landed receipts and replay-strengthening work
- directly improves governance/evidence usefulness without changing the ALLOW/DENY baseline
- narrower than global structural metering
- materially safer than introducing messaging triage / non-resolution

Ranked order:
1. Slice A — bounded provider-evidence / receipt-linkage strengthening
2. Slice B — structural rate-governance strengthening
3. Slice C — post-ALLOW evidence-contract clarification
4. Slice D — messaging triage / non-resolution extension

## 6. STOP_BOUNDARIES

- STOP if the chosen slice would require generic proxy infrastructure, content evaluation, or web/shell governance.
- STOP if provider-evidence strengthening cannot be separated cleanly from a broad export/proof lane.
- STOP if any proposed slice silently redefines messaging from ALLOW/DENY-only into a broader doctrine lane without separate canon support.
