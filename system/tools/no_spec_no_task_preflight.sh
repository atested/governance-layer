#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: no_spec_no_task_preflight.sh <TASK_ID>" >&2
  exit 2
fi

task_id="$1"

if ls "docs/dev/tasks/ready/${task_id}__"*.md >/dev/null 2>&1; then
  spec_path="$(ls "docs/dev/tasks/ready/${task_id}__"*.md | LC_ALL=C sort | head -n 1)"
  echo "SPEC_FOUND=$spec_path"
  exit 0
fi

if ls "docs/dev/tasks/proposed/${task_id}__"*.md >/dev/null 2>&1; then
  spec_path="$(ls "docs/dev/tasks/proposed/${task_id}__"*.md | LC_ALL=C sort | head -n 1)"
  echo "SPEC_FOUND=$spec_path"
  exit 0
fi

echo "STOP_REASON=SPEC_MISSING"
echo "TASK_ID=$task_id"
exit 3
