# TASK_414 — planning state refresh and remaining slice reassessment after T413 v1

## 1. PURPOSE

Refresh current-main planning truth after `TASK_413` and determine whether any packaged remaining slice is now the clear next bounded governance tranche.

## 2. PHASE_1_CURRENT_MAIN_EVIDENCE

- `TASK_413` is landed on current main and records three completed lanes:
  - external summary-contract parity residue audit
  - provider-evidence / receipt-linkage strengthening
  - Combo A structured summary emission
- Current-main implementation and test evidence matches that record:
  - `tests/test_external_summary_contract_parity_audit.sh`
  - `mcp/server.py`
  - `system/tests/test_mcp_msg_surface.sh`
  - `system/tests/test_mcp_msg_replay_receipt.sh`
  - `scripts/verify-chain.py`
  - `tests/test_rdd_chain_verify.sh`
  - `tests/test_rdd_terminal_judgment.sh`
- `CURRENT_MAIN_CAPABILITY_MAP.md`, `WORK_QUEUE.md`, and `POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md` were still describing the pre-T413 field and therefore lagged reachable current-main truth.

## 3. PHASE_1_REFRESH_ACTIONS

- Updated `CURRENT_MAIN_CAPABILITY_MAP.md` to:
  - reflect baseline `587cb02ece6fa246e0500e0c48e5e8a64b64217f`
  - record the three T413 slices as landed baseline
  - distinguish remaining residue from consumed packaged slices
  - move the control-plane outcome from formulation-only to one bounded next tranche being available
- Updated `WORK_QUEUE.md` control-plane note so it no longer describes the pre-T413 no-winner state.
- Updated `POST_REFRESH_NEXT_WORKFRONT_CONFIRMATION__v1.md` so it is explicitly historical/superseded rather than silently stale.
- Left `RECORD_TO_PACKET_NEXT_TRANCHE_CONFIRMATION__v1.md` unchanged because it was already truthful on its narrow point: replay-outcome propagation is consumed baseline and must not be re-dispatched.

## 4. PHASE_1_POST_REFRESH_STATE

Refreshed planning state is coherent enough for selection: `YES`.

Current-main truth after refresh:
- T413 consumed the first safe packaged slices in the external validator/operator hardening, messaging follow-on, and post-selector RDD residual lanes.
- The broader lanes behind those first slices remain live, but their remaining packaged residue is either:
  - riskier (`packet_hash` field-shape normalization),
  - broader / less bounded (remaining messaging follow-on),
  - or lower-leverage than the untouched GovCore correction package (post-selector continuation after Combo A).
- The untouched `TASK_412A` package remains bounded, current-main-supported, and not yet consumed.

## 5. CANDIDATES_CONSIDERED

### Candidate A — GovCore naming-correction implementation (`TASK_412A`)
- Still untouched after T413.
- Bounded to planning/reference language only.
- Current-main evidence still shows a small fixed set of references that present `GovCore` as a surface label.

### Candidate B — remaining messaging follow-on after provider-evidence strengthening
- First safe slice is consumed.
- Remaining slices are:
  - structural rate-governance strengthening
  - post-ALLOW evidence-contract clarification
  - triage / non-resolution extension
- These are still broader or less clearly leveraged than Candidate A.

### Candidate C — remaining external validator/operator hardening residue after parity audit
- First-ranked audit slice is consumed.
- The strongest concrete remaining item is `packet_hash` field-shape normalization.
- Current-main evidence still characterizes that item as a breaking-change-risk surface, not the obvious next bounded move.

### Candidate D — remaining post-selector RDD seam work after Combo A
- Combo A structured summary emission is consumed.
- Remaining shortlist item is chain verification terminal-presentation coherence.
- It remains lower priority and less directly current-main-pressing than Candidate A.

## 6. RECOMMENDED_NEXT_WORKFRONT

`SELECT_AND_PROCEED`

Recommended next workfront:
`GovCore reference audit and naming-correction implementation`

This is the implementation follow-on to the bounded plan packaged in `TASK_412A__govcore_reference_audit_and_naming_correction_plan__v1.md`.

## 7. WHY_THIS_NOW

- It is the strongest remaining packaged slice that is still both bounded and untouched by T413.
- It closes a real current-main governance-language defect:
  - repo planning/reference surfaces still present `GovCore` as if it were a governance surface peer, even though current-main boundary evidence does not support that.
- It outranks the remaining packaged residue because:
  - remaining messaging follow-on is still broader than one obvious safe slice,
  - remaining external validator residue still points first to a breaking-risk normalization item,
  - remaining post-selector work is real but lower leverage after Combo A landed.
- It can be dispatched next without reopening broader governance formulation, runtime redesign, or queue-wide reprioritization.

## 8. BOUNDS_AND_INVARIANTS

- Keep the next tranche confined to planning/reference language correction.
- Do not rename runtime/code/package surfaces.
- Do not use the tranche to invent a new governance surface in place of `GovCore`.
- Do not reopen `GovLayer`, `GovMCP`, messaging, proof/export, or RDD implementation lanes.
- Do not treat historical/planning references as proof that `GovCore` remains a peer surface.
- Preserve any references whose role is explicitly historical or comparative rather than actively teaching `GovCore` as a surface label.
