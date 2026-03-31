#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

out_ok="$($repo_root/system/tools/no_spec_no_task_preflight.sh TASK_204 2>&1)"
echo "$out_ok" | rg '^SPEC_FOUND=docs/dev/tasks/ready/TASK_204__no_spec_no_task_preflight.md$' >/dev/null

set +e
out_fail="$($repo_root/system/tools/no_spec_no_task_preflight.sh TASK_9999 2>&1)"
rc_fail=$?
set -e
[[ "$rc_fail" -eq 3 ]]
echo "$out_fail" | rg '^STOP_REASON=SPEC_MISSING$' >/dev/null
echo "$out_fail" | rg '^TASK_ID=TASK_9999$' >/dev/null

echo "TEST_NO_SPEC_NO_TASK_PREFLIGHT:PASS"
