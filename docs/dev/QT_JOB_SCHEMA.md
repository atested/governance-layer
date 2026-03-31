# QT_JOB_SCHEMA.md

Canonical schema for jobs executed by `system/scripts/qt-runner.sh`.

## Format

Job files are markdown with `KEY: value` header lines.

Required keys:
- `JOB_ID`: unique Qt job id (example: `QT_JOB_001`)
- `JOB_TYPE`: currently supported value is `merge_readiness`
- `TARGET_BRANCH`: branch to validate (example: `codex/TASK_071`)
- `TASK_ID`: task id for merge-readiness validation (example: `TASK_071`)
- `TASK_SPEC`: repo-relative path to task spec (example: `docs/dev/tasks/ready/TASK_071__name.md`)

Optional keys:
- `NOTES`: free-form notes

## merge_readiness checks

`qt-runner.sh` performs deterministic checks:
1. target branch is resolvable (`refs/heads/*` or `refs/remotes/origin/*`)
2. task spec exists on target branch
3. task spec declares matching `TASK_ID`
4. evidence file exists at `docs/dev/evidence/<TASK_ID>/TESTS.txt` on target branch
5. evidence file is non-empty and contains command/output markers
6. changed files in target branch vs `origin/main` comply with task allowlist patterns

## Outputs

Runner writes:
- `docs/dev/evidence/QT/<JOB_ID>/TESTS.txt`
- `docs/dev/evidence/QT/<JOB_ID>/QT_REPORT.md`

Runner exits non-zero on any failed check (fail closed).
