#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output="$($repo_root/system/tools/stop_packet_generator.sh \
  '2026-02-28T00:00:00Z' \
  '/repo/path' \
  'release-gate' \
  'GOV_PROFILE=dev bash system/scripts/release-gate.sh' \
  'exit=1')"

echo "$output" | sed -n '1p' | rg '^STOP PACKET$' >/dev/null
echo "$output" | sed -n '2p' | rg '^- Timestamp: 2026-02-28T00:00:00Z$' >/dev/null
echo "$output" | sed -n '3p' | rg '^- Repo: /repo/path$' >/dev/null
echo "$output" | sed -n '4p' | rg '^- Step failed: release-gate$' >/dev/null
echo "$output" | sed -n '5p' | rg '^- Command: GOV_PROFILE=dev bash system/scripts/release-gate.sh$' >/dev/null
echo "$output" | sed -n '6p' | rg '^- Output: exit=1$' >/dev/null

echo "TEST_STOP_PACKET_GENERATOR:PASS"
