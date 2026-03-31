# TASK_415 — GovCore reference audit and naming-correction implementation v1

## 1. PURPOSE

Implement the bounded current-main naming corrections authorized by `TASK_412A` so planning/reference surfaces no longer teach `GovCore` as a governance surface label.

## 2. SOURCE_PLAN_REFERENCE

- Source plan: `docs/dev/tasks/ready/TASK_412A__govcore_reference_audit_and_naming_correction_plan__v1.md`
- Selection confirmation: `docs/dev/tasks/ready/TASK_414__planning_state_refresh_and_remaining_slice_reassessment_after_t413__v1.md`
- Applied plan logic:
  - implement only the clean `RENAME` targets
  - leave `KEEP` targets unchanged
  - skip `UNRESOLVED` targets where current-main evidence did not make a no-risk local correction mandatory

## 3. TARGETS_IMPLEMENTED

- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T405__v1.md` — `RENAME`
  - title changed from `GovCore` framing to `Current-Main Governance` framing
- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md` — `RENAME`
  - title changed from `GovCore` framing to `Current-Main Governance` framing
- `docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md` — `RENAME`
  - title changed from `GovCore` framing to `Current-Main Governance` framing
- `docs/dev/tasks/ready/TASK_367__govlayer_trust_grade_closure_restock.md` — `RENAME`
  - layer-boundary bullet changed from `GovCore = main development target` to `governance-layer repo = main development target`

## 4. TARGETS_SKIPPED

- `docs/dev/tasks/ready/TASK_411__planning_state_refresh_and_next_workfront_selection_after_t410__v1.md`
  - `KEEP-NO-CHANGE`
  - current wording is historical/planning context about a candidate lane, not an active statement that `GovCore` is a peer governance surface
- `docs/dev/SHIPPED_BUNDLE_VALIDATOR_PARITY_AND_EXTERNAL_CONTRACT_CONVERGENCE__v1.md`
  - `SKIPPED`
  - `TASK_412A` marked this target `UNRESOLVED`
  - the local sentence is comparative shorthand rather than a clear peer-surface teaching statement, so current-main evidence did not require forcing a rename in this tranche

## 5. WORDING_CHANGES

- Replaced `GovCore` only where it functioned as a misleading planning umbrella or explicit surface/taxonomy label.
- Used narrow replacements tied to existing repo truth:
  - `Current-Main Governance` for broad-state and backlog titles
  - `governance-layer repo` for the explicit “main development target” taxonomy line
- Did not introduce a new umbrella surface or broad replacement term.
- Did not touch runtime, package, or code surfaces.

## 6. VERIFICATION

- Verified each changed file still reads truthfully after correction.
- Verified no changed file now presents `GovCore` as a peer to `GovLayer` or `GovMCP`.
- Verified no changed file introduces a new ambiguous umbrella label.
- Verified the unchanged `KEEP` target remains historical/planning context rather than active peer-surface teaching.
- Verified the unresolved parity/convergence target was left untouched rather than over-corrected.

## 7. STOP_BOUNDARIES

- Stop any target that requires broader reframing than a local wording correction.
- Stop any target whose surrounding sentence cannot be corrected without inventing a new governance surface.
- Stop any target that would require touching runtime/code/package surfaces instead of planning/reference language only.
