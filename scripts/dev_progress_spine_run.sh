#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: dev_progress_spine_run.sh

Runs the progress spine pipeline:
1) dev_phase2_regression.sh
2) dev_progress_status.sh
3) dev_next_actions_compiler.sh
4) dev_merge_sim_inputs_from_queue.sh

Environment:
- SPINE_SCRIPTS_DIR (default: scripts)
- SPINE_OUT_ROOT (default: out)
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -ne 0 ]]; then
  usage
  exit 1
fi

scripts_dir="${SPINE_SCRIPTS_DIR:-scripts}"
out_root="${SPINE_OUT_ROOT:-out}"

phase2_report="$out_root/phase2_reports/latest/report.v1.json"
status_report="$out_root/progress_status/latest/status.v1.json"
next_actions_report="$out_root/next_actions/latest/next_actions.v1.json"
merge_branches="$out_root/merge_sim_inputs/latest/branches.txt"

run_stage() {
  local stage="$1"
  shift
  if ! "$@" >/dev/null 2>&1; then
    echo "SPINE_STAGE_FAILED=$stage"
    exit 1
  fi
}

require_file() {
  local p="$1"
  local stage="$2"
  if [[ ! -f "$p" ]]; then
    echo "SPINE_STAGE_FAILED=$stage"
    exit 1
  fi
}

stage1="$scripts_dir/dev_phase2_regression.sh"
stage2="$scripts_dir/dev_progress_status.sh"
stage3="$scripts_dir/dev_next_actions_compiler.sh"
stage4="$scripts_dir/dev_merge_sim_inputs_from_queue.sh"

for s in "$stage1" "$stage2" "$stage3" "$stage4"; do
  if [[ ! -x "$s" && ! -f "$s" ]]; then
    echo "SPINE_STAGE_FAILED=PREREQ_MISSING"
    exit 1
  fi
done

run_stage "PHASE2_REGRESSION" bash "$stage1"
require_file "$phase2_report" "PHASE2_REGRESSION"

run_stage "STATUS_GENERATOR" bash "$stage2"
require_file "$status_report" "STATUS_GENERATOR"

run_stage "NEXT_ACTIONS" bash "$stage3"
require_file "$next_actions_report" "NEXT_ACTIONS"

set +e
bash "$stage4" >/dev/null 2>&1
rc4=$?
set -e
if [[ $rc4 -eq 0 ]]; then
  require_file "$merge_branches" "MERGE_SIM_INPUTS"
  merge_value="$merge_branches"
else
  if [[ -f "$merge_branches" ]] && grep -qx 'MERGE_SIM_INPUTS_EMPTY=YES' "$merge_branches"; then
    merge_value="EMPTY"
  else
    echo "SPINE_STAGE_FAILED=MERGE_SIM_INPUTS"
    exit 1
  fi
fi

echo "SPINE_RUN=PASS"
echo "REPORT_PHASE2=$phase2_report"
echo "REPORT_STATUS=$status_report"
echo "REPORT_NEXT_ACTIONS=$next_actions_report"
echo "MERGE_SIM_BRANCHES=$merge_value"
