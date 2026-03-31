# TASK_070__codex-unattended-allowed-files-parser.md

TASK_ID: TASK_070
Title: Broaden codex-unattended Allowed Files parser for mixed spec formats
Executor: UNASSIGNED
Status: Ready
Dependencies: none

## Goal
Update `system/scripts/codex-unattended.sh` so Allowed Files extraction accepts both section styles used by task specs while remaining fail-closed.

## Constraints
- Do not merge to main.
- Do not edit WORK_QUEUE.md.
- Do not edit docs/dev/ASSIGNMENTS.md.
- Deterministic outputs only (no timestamps/randomized behavior).
- Keep unattended verification fail-closed.
- Do not weaken cleanliness or evidence enforcement.

## Required changes
1) Extend parser in `parse_allowed_files` to support either section header (any capitalization):
- `Allowed Files`
- `Files allowed to touch`

2) Accept either entry style within the allowed section:
- bullet entries (`-` or `*`)
- plain line entries (path/glob lines)

3) Section stop conditions:
- next markdown header line that starts with `#`
- or header containing `Files forbidden to touch`

4) Ignore non-entry lines:
- blank lines
- `Everything else`
- numbered procedure lines like `1) ...`

5) Error behavior:
- return parsed globs/paths when either format yields entries
- error only when no Allowed Files entries can be parsed

## Files allowed to touch
- system/scripts/codex-unattended.sh
- docs/dev/tasks/ready/TASK_070__codex-unattended-allowed-files-parser.md
- docs/dev/evidence/TASK_070/**
- docs/dev/inventory/INVENTORY_LATEST.md

## Files forbidden to touch
Everything else.

## Test plan / evidence required
Create `docs/dev/evidence/TASK_070/TESTS.txt` with full output for:
- `bash system/scripts/codex-unattended.sh begin-task TASK_062`
- `bash system/scripts/codex-unattended.sh verify-task TASK_062`
- `bash -n system/scripts/codex-unattended.sh`
- `python3 scripts/verify-ops-canonical.py`
- `bash system/scripts/inventory-snapshot.sh`

## Acceptance criteria
- `begin-task TASK_062` prints the three Allowed Files entries from TASK_062 spec.
- `verify-task TASK_062` does not fail due to Allowed Files parse errors.
- `bash -n system/scripts/codex-unattended.sh` passes.
- ops canonical verification passes.
- Inventory snapshot runs successfully; include deterministic inventory update if changed.
