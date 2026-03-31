#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: release_gate_summary_parser.sh <release_gate_log>" >&2
  exit 2
fi
log_file="$1"
if [[ ! -f "$log_file" ]]; then
  echo "missing log file: $log_file" >&2
  exit 1
fi

pass_lines=$(rg -c '^PASS' "$log_file" || true)
fail_lines=$(rg -c '^FAIL' "$log_file" || true)

exit_line=$(rg -n '^\[exit=[0-9]+\]$' "$log_file" | tail -n 1 || true)
if [[ -n "$exit_line" ]]; then
  exit_code=$(echo "$exit_line" | sed -E 's/^.*\[exit=([0-9]+)\]$/\1/')
else
  exit_code="unknown"
fi

echo "PASS_LINES=$pass_lines"
echo "FAIL_LINES=$fail_lines"
echo "EXIT=$exit_code"
