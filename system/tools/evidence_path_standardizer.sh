#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: evidence_path_standardizer.sh <path>" >&2
  exit 2
fi

input="$1"
normalized="$(echo "$input" | sed -E 's#/{2,}#/#g; s#/$##')"

pattern='^docs/dev/evidence/TASK_[0-9]+/(TESTS\.txt|DIFF_NAME_ONLY\.txt|DIFF_STAT\.txt|HOTFILE_SCAN\.txt)$'
if echo "$normalized" | rg "$pattern" >/dev/null; then
  echo "EVIDENCE_PATH_VALID=$normalized"
  exit 0
fi

echo "EVIDENCE_PATH_INVALID=$normalized"
exit 3
