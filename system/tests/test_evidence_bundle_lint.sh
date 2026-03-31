#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

evidence_ok="$tmp_dir/evidence_ok"
mkdir -p "$evidence_ok"
for f in TESTS.txt DIFF_NAME_ONLY.txt DIFF_STAT.txt HOTFILE_SCAN.txt; do
  printf 'ok\n' > "$evidence_ok/$f"
done
printf 'docs/spec/process-ledger-v1.md\n' > "$evidence_ok/DIFF_NAME_ONLY.txt"

"$repo_root/system/tools/evidence_bundle_lint.sh" "$evidence_ok" "$evidence_ok/DIFF_NAME_ONLY.txt"

evidence_bad="$tmp_dir/evidence_bad"
mkdir -p "$evidence_bad"
for f in TESTS.txt DIFF_NAME_ONLY.txt DIFF_STAT.txt HOTFILE_SCAN.txt; do
  printf 'ok\n' > "$evidence_bad/$f"
done
printf 'system/scripts/release-gate.sh\n' > "$evidence_bad/DIFF_NAME_ONLY.txt"

set +e
"$repo_root/system/tools/evidence_bundle_lint.sh" "$evidence_bad" "$evidence_bad/DIFF_NAME_ONLY.txt" > "$tmp_dir/fail.out" 2>&1
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  echo "expected hot-file lint failure"
  exit 1
fi

echo "TEST_EVIDENCE_BUNDLE_LINT:PASS"
