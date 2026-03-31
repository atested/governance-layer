#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$($repo_root/system/tools/local_ci_minimal.sh 2>&1)"

echo "$out" | rg '^PASS:bash system/tests/test_hot_file_scan.sh$' >/dev/null
echo "$out" | rg '^PASS:bash system/tests/test_stop_packet_generator.sh$' >/dev/null
echo "$out" | rg '^SUMMARY_PASS=2$' >/dev/null
echo "$out" | rg '^SUMMARY_FAIL=0$' >/dev/null
echo "$out" | rg '^EXIT=0$' >/dev/null

echo "TEST_LOCAL_CI_MINIMAL:PASS"
