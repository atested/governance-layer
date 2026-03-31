#!/usr/bin/env bash
# Read-only throughput log reporter
# Parses /tmp/throughput*.log files and extracts key information
#
# Usage:
#   throughput-report.sh                    # Show all logs
#   throughput-report.sh --last 3           # Show last 3 logs
#   throughput-report.sh --task TASK_104    # Filter to TASK_104
#   throughput-report.sh --last 1 --task TASK_092  # Combined

set -euo pipefail

LAST_N=""
FILTER_TASK=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --last)
      LAST_N="${2:-}"
      if [[ -z "$LAST_N" || ! "$LAST_N" =~ ^[0-9]+$ ]]; then
        echo "ERROR: --last requires a number" >&2
        exit 1
      fi
      shift 2
      ;;
    --task)
      FILTER_TASK="${2:-}"
      if [[ -z "$FILTER_TASK" ]]; then
        echo "ERROR: --task requires a task ID" >&2
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      echo "Usage: throughput-report.sh [--last N] [--task TASK_###]" >&2
      exit 1
      ;;
  esac
done

# Find throughput log files (handle /tmp symlink on macOS)
LOGS=$(cd /tmp 2>/dev/null && ls -1 throughput*.log 2>/dev/null | sed 's|^|/tmp/|' | sort -t_ -k2 -n -r || true)

if [[ -z "$LOGS" ]]; then
  echo "No throughput logs found in /tmp/throughput*.log"
  exit 0
fi

# Limit to last N if specified
if [[ -n "$LAST_N" ]]; then
  LOGS=$(echo "$LOGS" | head -n "$LAST_N")
fi

# Process each log file
for log in $LOGS; do
  echo "========================================"
  echo "LOG: $(basename "$log")"
  echo "DATE: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$log" 2>/dev/null || date -r "$log" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "unknown")"
  echo "========================================"
  echo

  # Extract published task lines (format: TASK_### CODE|EVIDENCE_ONLY origin/codex/TASK_###__hash)
  echo "## Published Tasks"
  if grep -E '^TASK_[0-9]{3}\s+(CODE|EVIDENCE_ONLY)\s+origin/codex/TASK_[0-9]{3}__[a-f0-9]+' "$log" > /dev/null 2>&1; then
    if [[ -n "$FILTER_TASK" ]]; then
      grep -E "^${FILTER_TASK}\s+(CODE|EVIDENCE_ONLY)\s+origin/codex/${FILTER_TASK}__[a-f0-9]+" "$log" || echo "(none matching $FILTER_TASK)"
    else
      grep -E '^TASK_[0-9]{3}\s+(CODE|EVIDENCE_ONLY)\s+origin/codex/TASK_[0-9]{3}__[a-f0-9]+' "$log"
    fi
  else
    echo "(none)"
  fi
  echo

  # Extract error/stop/timeout lines
  echo "## Errors and Stops"
  if grep -iE '(STOP:|fatal:|TIMEOUT|ERROR:)' "$log" > /dev/null 2>&1; then
    if [[ -n "$FILTER_TASK" ]]; then
      # Show context around filtered task
      grep -iE "(STOP:|fatal:|TIMEOUT|ERROR:)" "$log" | grep -i "$FILTER_TASK" || echo "(none for $FILTER_TASK)"
    else
      grep -iE '(STOP:|fatal:|TIMEOUT|ERROR:)' "$log" | head -20
    fi
  else
    echo "(none)"
  fi
  echo

  # Extract final summary (CODE: X, EVIDENCE_ONLY: Y)
  echo "## Summary"
  if grep -E '^CODE: [0-9]+, EVIDENCE_ONLY: [0-9]+' "$log" > /dev/null 2>&1; then
    grep -E '^CODE: [0-9]+, EVIDENCE_ONLY: [0-9]+' "$log" | tail -1
  else
    echo "(no summary line)"
  fi
  echo

  # Extract execution time if present
  if grep -E '^(real|user|sys)\s+[0-9]+m[0-9]+' "$log" > /dev/null 2>&1; then
    echo "## Execution Time"
    grep -E '^(real|user|sys)\s+[0-9]+m[0-9]+' "$log"
    echo
  fi
done

# Overall summary across all selected logs
echo "========================================"
echo "OVERALL SUMMARY (all selected logs)"
echo "========================================"
echo

set +e  # Disable exit-on-error for summary calculation
TOTAL_CODE=0
TOTAL_EVIDENCE=0

for log in $LOGS; do
  CODE_COUNT=$(grep -c '^TASK_[0-9][0-9][0-9].*CODE' "$log" 2>/dev/null | head -1)
  EVIDENCE_COUNT=$(grep -c '^TASK_[0-9][0-9][0-9].*EVIDENCE_ONLY' "$log" 2>/dev/null | head -1)
  CODE_COUNT=${CODE_COUNT:-0}
  EVIDENCE_COUNT=${EVIDENCE_COUNT:-0}
  TOTAL_CODE=$((TOTAL_CODE + CODE_COUNT))
  TOTAL_EVIDENCE=$((TOTAL_EVIDENCE + EVIDENCE_COUNT))
done
set -e  # Re-enable exit-on-error

echo "Total CODE: $TOTAL_CODE"
echo "Total EVIDENCE_ONLY: $TOTAL_EVIDENCE"
echo "Total tasks: $((TOTAL_CODE + TOTAL_EVIDENCE))"
NUM_LOGS=$(echo "$LOGS" | wc -w)
echo "Logs analyzed: $NUM_LOGS"
