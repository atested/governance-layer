#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

out_ok="$($repo_root/system/tools/evidence_path_standardizer.sh 'docs/dev/evidence//TASK_202/TESTS.txt/' 2>&1)"
echo "$out_ok" | rg '^EVIDENCE_PATH_VALID=docs/dev/evidence/TASK_202/TESTS.txt$' >/dev/null

set +e
out_bad="$($repo_root/system/tools/evidence_path_standardizer.sh 'docs/dev/evidence/TASK_202/OTHER.txt' 2>&1)"
rc_bad=$?
set -e
[[ "$rc_bad" -eq 3 ]]
echo "$out_bad" | rg '^EVIDENCE_PATH_INVALID=docs/dev/evidence/TASK_202/OTHER.txt$' >/dev/null

echo "TEST_EVIDENCE_PATH_STANDARDIZER:PASS"
