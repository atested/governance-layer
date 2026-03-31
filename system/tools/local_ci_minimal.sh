#!/bin/bash
set -euo pipefail

checks=(
  "bash system/tests/test_hot_file_scan.sh"
  "bash system/tests/test_stop_packet_generator.sh"
)

pass=0
fail=0
for cmd in "${checks[@]}"; do
  if bash -lc "$cmd" >/dev/null 2>&1; then
    echo "PASS:$cmd"
    pass=$((pass + 1))
  else
    echo "FAIL:$cmd"
    fail=$((fail + 1))
  fi
done

echo "SUMMARY_PASS=$pass"
echo "SUMMARY_FAIL=$fail"
if [[ "$fail" -eq 0 ]]; then
  echo "EXIT=0"
  exit 0
fi

echo "EXIT=1"
exit 1
