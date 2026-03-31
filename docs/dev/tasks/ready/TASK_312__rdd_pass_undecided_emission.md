# TASK_312 — RDD: Pass UNDECIDED emission — FS_COPY dest-exists

SPEC_EXPECTED: CODE

## Intent

Extend the FS_COPY branch of `scripts/policy-eval.py` to emit `UNDECIDED` instead of `DENY` when the destination path exists and overwrite was not requested. This implements the first real UNDECIDED boundary per the accepted Phase 0 schema contract.

The change is a behavioral modification to one existing condition (`REASON_DEST_EXISTS` for FS_COPY). All other FS_COPY cases and all other tool cases are unchanged.

## Behavioral change

**Before (current behavior)**:
When `canon_dst.exists() and not overwrite_requested` in the FS_COPY branch:
- adds `REASON_DEST_EXISTS` to `policy_reasons`
- record emits `"policy_decision": "DENY"`

**After (this task)**:
When `canon_dst.exists() and not overwrite_requested` in the FS_COPY branch:
- does NOT add `REASON_DEST_EXISTS` to `policy_reasons`
- sets `"policy_decision": "UNDECIDED"`
- sets `"policy_reasons": []`
- adds `insufficiency` block (see schema below)
- proceeds to `emit_record` as normal

The gate behavior is unchanged: `UNDECIDED` is not `ALLOW`. The caller (shell script or MCP server) determines gate outcome from `policy_decision`. UNDECIDED means the gate stays closed.

## Insufficiency block schema

The `insufficiency` block must be exactly:

```json
{
  "trigger": "dest_exists_no_overwrite",
  "surface": "filesystem",
  "tool": "FS_COPY",
  "condition": "Destination path exists and overwrite was not requested",
  "rules_consulted": ["FS_COPY.caps.overwrite_allowed"],
  "gap": "No rule specifies disposition when destination exists and overwrite is not requested. The overwrite policy governs whether overwrite is permitted when requested, not what to do when it is not requested and the destination exists."
}
```

The `insufficiency` block must be present if and only if `policy_decision` is `"UNDECIDED"`.
The `insufficiency` block must not classify the insufficiency — no `category`, `deficiency_class`, or similar judgment fields.

## Acceptance criteria

- FS_COPY with existing destination and `overwrite=false` produces `"policy_decision": "UNDECIDED"`
- That record has `"policy_reasons": []`
- That record has `"insufficiency"` block with all five fields matching the schema above
- `insufficiency.gap` text is exactly as specified (no paraphrase)
- FS_COPY with non-existing destination produces `"policy_decision": "ALLOW"` unchanged
- FS_COPY with `overwrite=true` and overwrite allowed continues to produce `"policy_decision": "ALLOW"` unchanged
- FS_COPY with `overwrite=true` and overwrite forbidden continues to produce `"policy_decision": "DENY"` with `REASON_OVERWRITE_FORBIDDEN` unchanged
- FS_COPY outside allowed root continues to produce `"policy_decision": "DENY"` unchanged
- All non-FS_COPY tools continue to behave identically
- Record also contains `record_version: "0.2"`, `record_type: "pass_decision"`, `process_id` from TASK_311

## Files allowed to touch

- `scripts/policy-eval.py`
- `tests/fixtures/fs_copy_dest_exists_undecided.json` — new fixture file for the UNDECIDED case
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_312/**`

## Files forbidden to touch

- `docs/dev/ASSIGNMENTS.md`
- `docs/dev/WORK_QUEUE.md`
- `capabilities/capability-registry.json`
- `mcp/server.py`
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- `system/scripts/codex-unattended.sh`
- Any existing test files — regression test updates are TASK_313 scope
- Everything else.

## New fixture: `tests/fixtures/fs_copy_dest_exists_undecided.json`

Create this fixture file. It must be a valid intent JSON for FS_COPY where the destination path is a file that exists at test time. Use a path under the repo's `out/` directory (e.g., `out/rdd/test-dest-exists.txt`) that the test can create before invoking policy-eval.py.

The intent must include:
- `tool`: `"FS_COPY"`
- `args.src_path`: a valid path under an allowlisted directory
- `args.dst_path`: a path under an allowlisted directory that the test creates before invocation
- `args.overwrite`: `false`
- `intent.goal`: non-empty string
- `intent.expected_outputs`: non-empty array

## Required evidence artifacts

- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_312/TESTS.txt` — manual policy-eval.py invocation showing UNDECIDED output with correct fields; show at least: a UNDECIDED case and an unaffected ALLOW case
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_312/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_312/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_312/HOTFILE_SCAN.txt`

## Determinism expectations

- UNDECIDED output is deterministic for the same input: same `session_id`, `request_id`, and filesystem state produce the same `policy_decision`, `insufficiency` block, and `process_id`

## STOP rules

- STOP if implementing UNDECIDED requires touching any file not in the allowed list
- STOP if the behavioral change affects any case other than FS_COPY dest-exists-no-overwrite
- STOP if `insufficiency` block structure requires a new import or dependency not already in `policy-eval.py`
- STOP if `emit_record` needs changes to handle UNDECIDED (it should not — `policy_decision` is already a string field)
- STOP if forbidden files must be edited

## Constraints

- Scope: one condition in one branch of one evaluator. Nothing else.
- Do not implement Triage, chain verification changes, or signal collection — those are Phases 2–4.
- Do not add UNDECIDED to any other case class — the FS_COPY dest-exists case is the only v1 UNDECIDED case.
- Do not modify what the caller does with UNDECIDED — that is separate wiring work, not in this task.
