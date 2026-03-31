# DISPATCH_LIBRARY__CECIL_CODEX__v10

## Mandatory Preflight: TASK ID / branch collision guard
For any restock or publish batch, run the guard before creating specs or publishing branches:

```bash
system/scripts/task-id-guard.sh --base origin/main --task-ids <TASK_IDS...> --branches <BRANCH_NAMES...>
```

Fail-closed contract:
- Any `TASK_ID_CHECK FAIL ...` line => STOP.
- Any `BRANCH_CHECK FAIL ...` line => STOP.
- Any non-zero exit => STOP.
- Do not continue batch execution after guard failure.

Output contract consumed by automation:
- `TASK_SPEC_ROOT=<path>`
- `TASK_ID_CHECK PASS|FAIL <TASK_ID> <details>`
- `BRANCH_CHECK PASS|FAIL <branch> <details>`

This preflight is required for all restock/publish dispatches.

## Codex validation-scope expansion contract (sensitive surfaces)

For Codex implementation dispatches, include these required fields when validation-sensitive surfaces are touched:
- `TOUCHED_SENSITIVE_SURFACES`
- `REQUIRED_ADJACENT_GATES`
- `ADJACENT_GATE_STATUS`
- `MISSING_GATE_COVERAGE`

Fail-closed rule:
- If required adjacent gate coverage cannot be completed within allowed scope, STOP.

Initial proven sensitive-surface family:
- `scripts/policy-eval.py`
- `scripts/verify-record.py`
- signing preimage logic
- record hash construction
- signed emission field selection

Required adjacent gates for this family:
- `tests/test_signing_emit.sh`
- `tests/test_signing_determinism.sh`

Completion packet requirement for applicable Codex runs:
- Must report all four fields above explicitly.
- `ADJACENT_GATE_STATUS` must be `PASS` only when all required adjacent gates pass.
- `MISSING_GATE_COVERAGE` must be `NONE` for publishable handoff.

## Cecil merge completion control-plane sync fields

For Cecil merge dispatches and merge completion packets, require a lightweight control-plane sync disposition at merge closeout.

Minimum merge-exit questions:
- Did the merge land a new capability or governed surface?
- Did the merge materially consume a previously live tranche or family?
- Did the merge invalidate or materially weaken the current next-workfront recommendation?
- Did the merge make an existing family label or canonical planning statement stale or misleading?

Disposition rule:
- If all answers are `NO`: `CANON_SYNC_DISPOSITION: NONE`
- If any answer is `YES` and the sync is narrow and unambiguous: `CANON_SYNC_DISPOSITION: UPDATED_NOW`
- If any answer is `YES` and the sync needs broader synthesis: `CANON_SYNC_DISPOSITION: FOLLOW_ON_REQUIRED`

Required merge completion packet fields:
- `CONTROL_PLANE_TRUTH_CHANGED: YES/NO`
- `CANON_SYNC_DISPOSITION: NONE / UPDATED_NOW / FOLLOW_ON_REQUIRED`
- `CANON_SURFACES_UPDATED: <list or none>`
- `FOLLOW_ON_SYNC_TASK_REQUIRED: YES/NO`
- `WHY_NOT_UPDATED_IN_MERGE: <required only if FOLLOW_ON_REQUIRED>`
