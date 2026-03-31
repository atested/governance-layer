# TASK_313 — RDD: Pass UNDECIDED test coverage

SPEC_EXPECTED: CODE

## Intent

Add a dedicated test script covering the UNDECIDED emission path introduced in TASK_312 and regression coverage for all affected existing behaviors. This closes the test gap for the Phase 1 schema changes (TASK_311) and behavioral change (TASK_312).

## Test cases required

The test script must implement the following named test cases:

**UNDECIDED path tests** (new behavior from TASK_312):

| Test ID | Description | Expected outcome |
|---|---|---|
| T-UNDECIDED-001 | FS_COPY, dest exists, overwrite=false | `policy_decision` = `"UNDECIDED"` |
| T-UNDECIDED-002 | FS_COPY, dest exists, overwrite=false | `policy_reasons` = `[]` (empty array) |
| T-UNDECIDED-003 | FS_COPY, dest exists, overwrite=false | `insufficiency.trigger` = `"dest_exists_no_overwrite"` |
| T-UNDECIDED-004 | FS_COPY, dest exists, overwrite=false | `insufficiency.surface` = `"filesystem"` |
| T-UNDECIDED-005 | FS_COPY, dest exists, overwrite=false | `insufficiency.tool` = `"FS_COPY"` |
| T-UNDECIDED-006 | FS_COPY, dest exists, overwrite=false | `insufficiency` block is present |
| T-UNDECIDED-007 | FS_COPY, dest exists, overwrite=false | `record_type` = `"pass_decision"` |
| T-UNDECIDED-008 | FS_COPY, dest exists, overwrite=false | `process_id` is present and 16 hex chars |

**Regression tests** (existing behavior must be preserved):

| Test ID | Description | Expected outcome |
|---|---|---|
| T-REG-001 | FS_COPY, dest does NOT exist, overwrite=false | `policy_decision` = `"ALLOW"` |
| T-REG-002 | FS_COPY, dest exists, overwrite=true, overwrite_allowed=true | `policy_decision` = `"ALLOW"` |
| T-REG-003 | FS_COPY, src outside allowed root | `policy_decision` = `"DENY"` |
| T-REG-004 | FS_COPY, dst is hot file | `policy_decision` = `"DENY"` |
| T-REG-005 | FS_WRITE normal allow case | `policy_decision` = `"ALLOW"`, `record_type` = `"pass_decision"` |
| T-REG-006 | FS_WRITE normal allow case | `record_version` = `"0.2"` |
| T-REG-007 | FS_MOVE outside allowed root | `policy_decision` = `"DENY"` |

**Test setup requirements**:
- T-UNDECIDED-001 through T-UNDECIDED-008: test script must create a temporary destination file (e.g., in `$TMPDIR` or `out/rdd/`) before invoking policy-eval.py, and clean it up after
- T-REG-001: test script must verify the destination does NOT exist before invoking (or use a path that never exists in the test environment)
- T-REG-002: requires a capability registry entry where `overwrite_allowed=true` for FS_COPY, OR use a permissive fixture if available

## Acceptance criteria

- All test cases above pass
- Test script exits 0 only if all tests pass; exits non-zero on any failure
- Test output shows PASS/FAIL per test case with test ID
- Final line shows aggregate: `PASS: N  FAIL: 0` (or equivalent)
- No existing tests are broken by this task

## Files allowed to touch

- `tests/test_policy_pass_undecided.sh` — new test script
- `tests/fixtures/fs_copy_dest_exists_undecided.json` — if TASK_312 did not fully populate this fixture, complete it here
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_313/**`

## Files forbidden to touch

- `scripts/policy-eval.py` — no implementation changes in this task
- `docs/dev/ASSIGNMENTS.md`
- `docs/dev/WORK_QUEUE.md`
- `capabilities/capability-registry.json`
- `mcp/server.py`
- `system/scripts/release-gate.sh`
- `system/scripts/validate-proof-bundle.sh`
- `system/scripts/codex-unattended.sh`
- Any existing test files — regression is by running them, not by modifying them
- Everything else.

## Required evidence artifacts

- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_313/TESTS.txt` — full output of `tests/test_policy_pass_undecided.sh` showing all test IDs and PASS/FAIL; final aggregate line must show FAIL: 0
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_313/DIFF_NAME_ONLY.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_313/DIFF_STAT.txt`
- `docs/dev/evidence/RDD_PASS_UNDECIDED__v1/TASK_313/HOTFILE_SCAN.txt`

## Determinism expectations

- Test script produces identical output on repeated runs under identical filesystem state
- Test script is self-contained: creates and cleans up any temp files it needs

## STOP rules

- STOP if T-REG-002 cannot be implemented without modifying capability-registry.json or policy-eval.py (report as a planning gap; skip that test case with a documented reason rather than touching forbidden files)
- STOP if any existing test is broken by this task (test failures from TASK_311 or TASK_312 scope must have been resolved before TASK_313 begins)
- STOP if forbidden files must be edited

## Constraints

- Test script covers UNDECIDED path and regression only. No new implementation.
- Do not test Triage, chain verification, or signal extraction — those are Phases 2–4.
- Test ID naming (`T-UNDECIDED-NNN`, `T-REG-NNN`) must be used exactly as specified — these appear in evidence and review.
