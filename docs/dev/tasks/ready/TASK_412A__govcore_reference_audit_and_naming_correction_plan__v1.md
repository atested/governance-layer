# TASK_412A — GovCore reference audit and naming-correction plan v1

## 1. PURPOSE

Audit current-main references that still treat `GovCore` as a governance surface, then classify each reference as `KEEP`, `RENAME`, `REMOVE`, or `UNRESOLVED` without performing broad repo renaming. The goal is to package a bounded correction plan from current-main truth after `GovCore` was judged too weak to keep as a peer surface label.

## 2. CURRENT_MAIN_REFERENCES

- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T405__v1.md`
- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`
- `docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`
- `docs/dev/SHIPPED_BUNDLE_VALIDATOR_PARITY_AND_EXTERNAL_CONTRACT_CONVERGENCE__v1.md`
- `docs/dev/tasks/ready/TASK_367__govlayer_trust_grade_closure_restock.md`
- `docs/dev/tasks/ready/TASK_411__planning_state_refresh_and_next_workfront_selection_after_t410__v1.md`

These are the strongest current-main references surfaced by repo search outside review-corpus/evidence mirrors.

## 3. CLASSIFICATION_TABLE

| Reference | Current role | Classification | Reason |
|---|---|---|---|
| `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T405__v1.md` | broad planning-state label | `RENAME` | Uses `GovCore` as a planning umbrella, not as an explicit runtime or governance surface |
| `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md` | broad planning-state label | `RENAME` | Same issue; planning truth is real but the surface label is misleading |
| `docs/dev/GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md` | backlog grouping label | `RENAME` | Groups cross-lane design backlog rather than describing a defined surface boundary |
| `docs/dev/tasks/ready/TASK_367__govlayer_trust_grade_closure_restock.md` | explicit layer taxonomy claim | `RENAME` | `GovCore = main development target` conflicts with current-main boundary evidence that favors GovLayer/GovMCP plus planning labels |
| `docs/dev/tasks/ready/TASK_411__planning_state_refresh_and_next_workfront_selection_after_t410__v1.md` | candidate lane wording | `KEEP` | Retains historical planning context without itself asserting GovCore is a valid peer surface |
| `docs/dev/SHIPPED_BUNDLE_VALIDATOR_PARITY_AND_EXTERNAL_CONTRACT_CONVERGENCE__v1.md` | single sentence using GovCore claim wording | `UNRESOLVED` | Needs bounded local inspection during correction so wording is not over-fixed if the sentence is only comparative shorthand |

## 4. KEEP_RENAME_REMOVE_LOGIC

- `KEEP` only when the reference is clearly historical, comparative, or scoped so it does not present `GovCore` as an active governance surface.
- `RENAME` when the underlying planning truth is still valid but the `GovCore` label adds false symmetry with `GovLayer` and `GovMCP`.
- `REMOVE` only if the reference exists solely to assert a false surface boundary and carries no remaining planning value.
- `UNRESOLVED` when current-main evidence shows the term appears, but the surrounding sentence must be examined locally during correction to avoid deleting valid adjacent meaning.

## 5. BOUNDED_CORRECTION_PLAN

1. Correct planning-state and backlog artifacts first:
   - `GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T405__v1.md`
   - `GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`
   - `GOVCORE_DESIGN_BACKLOG_EXTRACTION__v1.md`
2. Replace `GovCore` with a truthful planning label such as `current-main governance backlog`, `governance design backlog`, or another repo-grounded non-surface label chosen file-by-file.
3. Correct explicit layer-taxonomy wording in `TASK_367__govlayer_trust_grade_closure_restock.md` so it no longer teaches `GovCore` as a peer or primary surface.
4. Inspect the single parity/convergence doc occurrence and either rename or leave it if the usage is merely historical shorthand.
5. Exclude broad filename churn, repo-wide renames, or canonical surface redesign from the correction tranche.

## 6. STOP_BOUNDARIES

- STOP if any target reference turns out to be consumed historical evidence that cannot be renamed without falsifying merged context.
- STOP if the correction would require renaming runtime/code/package surfaces instead of planning/reference language only.
- STOP if any replacement term would require inventing a new governance surface rather than removing false symmetry.
