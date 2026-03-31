#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# discover known existing TASK id on origin/main
known_task="$(git ls-tree -r --name-only origin/main -- docs/dev/tasks | rg -o 'TASK_[0-9]{3}' | sort -u | head -n 1)"
[[ -n "$known_task" ]]

# discover known existing remote codex branch
known_branch="$(git ls-remote --heads origin 'refs/heads/codex/*' | awk '{print $2}' | sed 's#refs/heads/##' | sort | head -n 1)"
[[ -n "$known_branch" ]]

# case 1: existing task id should fail
set +e
out1="$(system/scripts/task-id-guard.sh --base origin/main --task-ids "$known_task" --branches codex/DOES_NOT_EXIST__999999 2>&1)"
rc1=$?
set -e
[[ "$rc1" -ne 0 ]]
printf '%s\n' "$out1" | rg '^TASK_SPEC_ROOT=' >/dev/null
printf '%s\n' "$out1" | rg "^TASK_ID_CHECK FAIL ${known_task} hits=" >/dev/null
printf '%s\n' "$out1" | rg '^BRANCH_CHECK PASS codex/DOES_NOT_EXIST__999999 remote_hits=0$' >/dev/null

# case 2: existing remote branch should fail
set +e
out2="$(system/scripts/task-id-guard.sh --base origin/main --task-ids TASK_999999 --branches "$known_branch" 2>&1)"
rc2=$?
set -e
[[ "$rc2" -ne 0 ]]
printf '%s\n' "$out2" | rg '^TASK_ID_CHECK PASS TASK_999999 hits=0$' >/dev/null
printf '%s\n' "$out2" | rg "^BRANCH_CHECK FAIL ${known_branch} remote_hits=" >/dev/null

# case 3: clean pass
out3="$(system/scripts/task-id-guard.sh --base origin/main --task-ids TASK_999999 --branches codex/DOES_NOT_EXIST__999999 2>&1)"
printf '%s\n' "$out3" | rg '^TASK_SPEC_ROOT=' >/dev/null
printf '%s\n' "$out3" | rg '^TASK_ID_CHECK PASS TASK_999999 hits=0$' >/dev/null
printf '%s\n' "$out3" | rg '^BRANCH_CHECK PASS codex/DOES_NOT_EXIST__999999 remote_hits=0$' >/dev/null

echo "PASS test_task_id_guard"
