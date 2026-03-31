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
