#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: repo_tripwire.sh <execution_root> <target_path>" >&2
  exit 2
fi

execution_root="$1"
target_path="$2"

root_real="$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$execution_root")"
target_real="$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$target_path")"

if [[ "$target_real" == "$root_real" || "$target_real" == "$root_real"/* ]]; then
  echo "TRIPWIRE_PASS"
  echo "EXECUTION_ROOT=$root_real"
  echo "TARGET_PATH=$target_real"
  exit 0
fi

echo "WRONG_EXECUTION_ROOT"
echo "EXECUTION_ROOT=$root_real"
echo "TARGET_PATH=$target_real"
exit 3
