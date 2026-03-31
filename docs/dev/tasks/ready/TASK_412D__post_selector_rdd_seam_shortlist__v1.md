# TASK_412D — Post-selector RDD seam shortlist v1

## 1. PURPOSE

Inventory remaining post-selector RDD seams on current main, filter them for boundedness and distinctness from the consumed selector-mode family, and shortlist only the seams that are dispatchable as next slices.

## 2. CURRENT_MAIN_RDD_SEAMS

Current-main evidence:

- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
  - phases 1–11 landed
  - explicit deferrals remain
- `docs/dev/RDD_SELECTOR_MODE_TRANCHE_POST_IMPLEMENTATION_REVIEW__v1.md`
  - selector-mode family is materially consumed
- `docs/dev/POST_SELECTOR_DOCTRINE_FORMULATION__v1.md`
  - packages bounded post-selector candidates
- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`
  - says the only non-deferred live residue is Combo A structured summary emission

Current-main candidate seams surfaced by these artifacts:
- Combo A structured summary emission (`verify-chain.py` to structured JSON)
- chain verification plus terminal-presentation coherence
- second case-class / broader doctrine continuation
- terminal judgment runtime

## 3. BOUNDEDNESS_FILTER

A seam is shortlistable only if it:
- is distinct from the consumed selector-mode family
- is not explicitly deferred by the implementation plan unless separately restocked
- has a clear bounded artifact target
- does not require general doctrine redesign or multi-case expansion

Excluded by this filter:
- terminal judgment runtime
- multi-case-class continuation
- broad selector/doctrine restocking

## 4. SHORTLISTED_SEAMS

### 1. Combo A structured summary emission
- Strongest dispatchable seam
- Direct bounded artifact target: structured chain-verification JSON
- Explicitly identified in current-main planning as the only non-deferred live residue

### 2. Chain verification terminal-presentation coherence
- Dispatchable only as a narrowly bounded doctrine/spec slice
- Supported by `docs/dev/CHAIN_VERIFICATION_TERMINAL_JUDGMENT_SPEC__v1.md`
- Lower priority than Combo A because current-main broad-state truth names Combo A more directly

## 5. NON_DISPATCHABLE_SEAMS

- **Terminal judgment runtime**
  - explicitly deferred in the implementation plan
  - not safe as the next bounded slice from current-main truth
- **Second UNDECIDED case class / multi-case selector expansion**
  - design-blocked and broader than a next slice
- **General post-selector doctrine continuation**
  - too broad unless reduced to a specific bounded artifact seam

## 6. STOP_BOUNDARIES

- STOP if a proposed seam depends on reopening selector-mode closure claims.
- STOP if a seam requires multi-case or multi-domain redesign to justify itself.
- STOP if the only support for a seam is queue momentum rather than current-main doctrine/planning evidence.
