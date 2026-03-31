#!/bin/bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: stop_packet_generator.sh <timestamp> <repo> <step_failed> <command> <output>" >&2
  exit 2
fi

timestamp="$1"
repo="$2"
step_failed="$3"
command="$4"
output="$5"

cat <<EOT
STOP PACKET
- Timestamp: $timestamp
- Repo: $repo
- Step failed: $step_failed
- Command: $command
- Output: $output
EOT
