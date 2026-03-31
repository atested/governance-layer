#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: dev_merge_rehearsal_from_spine.sh [--branches-file PATH]

Runs merge rehearsal via dev_merge_window_simulator.sh using generated branches input.
Environment:
- MERGE_REHEARSAL_REPO=<path>  optional simulator repo override
USAGE
}

branches_file="out/merge_sim_inputs/latest/branches.txt"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branches-file)
      branches_file="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      usage
      exit 1 ;;
  esac
done

if [[ ! -f "$branches_file" ]] || grep -qx 'MERGE_SIM_INPUTS_EMPTY=YES' "$branches_file"; then
  echo "MERGE_REHEARSAL_SKIPPED=NO_BRANCHES"
  exit 0
fi

if [[ ! -s "$branches_file" ]]; then
  echo "MERGE_REHEARSAL_SKIPPED=NO_BRANCHES"
  exit 0
fi

if [[ ! -f scripts/dev_merge_window_simulator.sh ]]; then
  echo "MERGE_REHEARSAL_SKIPPED=NO_SIMULATOR"
  exit 0
fi

short_sha="$(git rev-parse --short origin/main 2>/dev/null || true)"
if [[ -z "$short_sha" ]]; then
  mseq="SIM_MAIN"
else
  mseq="SIM_${short_sha}"
fi

repo_override="${MERGE_REHEARSAL_REPO:-}"
repo_args=()
if [[ -n "$repo_override" ]]; then
  repo_args+=(--repo "$repo_override")
fi

bash scripts/dev_merge_window_simulator.sh \
  --mseq "$mseq" \
  --base origin/main \
  --branches "$branches_file" \
  --test-cmd "bash system/tests/test_no_conflict_markers_tracked.sh" \
  --test-cmd "bash system/tests/test_no_absolute_paths_tracked.sh" \
  --test-cmd "bash system/tests/test_no_trailing_whitespace.sh" \
  "${repo_args[@]}" >/dev/null 2>&1

rel_out_dir="out/merge_windows/${mseq}/"
if [[ -n "$repo_override" ]]; then
  check_dir="$repo_override/$rel_out_dir"
else
  check_dir="$rel_out_dir"
fi

if [[ -f "${check_dir}COMPLETION_PACKET.txt" ]]; then
  packet="COMPLETION_PACKET.txt"
elif [[ -f "${check_dir}STOP_PACKET.txt" ]]; then
  packet="STOP_PACKET.txt"
else
  echo "MERGE_REHEARSAL_SKIPPED=NO_PACKET"
  exit 0
fi

echo "MERGE_REHEARSAL_OUT=$rel_out_dir"
echo "MERGE_REHEARSAL_PACKET=$packet"
