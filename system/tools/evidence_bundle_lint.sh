#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: evidence_bundle_lint.sh <evidence_dir> <diff_name_only_file>" >&2
  exit 2
fi

evidence_dir="$1"
diff_file="$2"
required=(
  "TESTS.txt"
  "DIFF_NAME_ONLY.txt"
  "DIFF_STAT.txt"
  "HOTFILE_SCAN.txt"
)

for name in "${required[@]}"; do
  if [[ ! -f "$evidence_dir/$name" ]]; then
    echo "MISSING:$name"
    exit 1
  fi
done

hot_regex='^(system/scripts/release-gate\.sh|system/scripts/validate-proof-bundle\.sh|system/scripts/codex-unattended\.sh|docs/dev/WORK_QUEUE\.md|docs/dev/ASSIGNMENTS\.md)$'
if LC_ALL=C sort "$diff_file" | rg -n "${hot_regex}" >/dev/null; then
  echo "HOTFILE_HIT"
  LC_ALL=C sort "$diff_file" | rg -n "${hot_regex}" | sed 's/^/HOT:/'
  exit 1
fi

echo "EVIDENCE_BUNDLE_LINT:PASS"
exit 0
