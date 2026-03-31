#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage: system/scripts/task-id-guard.sh [--base <ref>] --task-ids <TASK_...> --branches <branch...>

Required:
  --task-ids   one or more explicit TASK IDs
  --branches   one or more explicit branch names
Optional:
  --base       git ref used for task ID scan (default: origin/main)
EOF
}

discover_task_spec_root() {
  local base_ref="$1"
  local first
  first="$(git ls-tree -r --name-only "$base_ref" -- docs | rg -m1 'TASK_[0-9]{3}__.*\.md$' || true)"
  if [[ -z "$first" ]]; then
    echo ""
    return 1
  fi

  local d b
  d="$(dirname "$first")"
  b="$(basename "$d")"
  case "$b" in
    ready|blocked|proposed)
      dirname "$d"
      ;;
    *)
      echo "$d"
      ;;
  esac
}

BASE_REF="origin/main"
TASK_IDS=()
BRANCHES=()
mode=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      [[ $# -ge 2 ]] || { echo "FAIL ARG missing_base_value"; exit 2; }
      BASE_REF="$2"
      shift 2
      ;;
    --task-ids)
      mode="task"
      shift
      ;;
    --branches)
      mode="branch"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "FAIL ARG unknown_option=$1"
      exit 2
      ;;
    *)
      if [[ "$mode" == "task" ]]; then
        TASK_IDS+=("$1")
      elif [[ "$mode" == "branch" ]]; then
        BRANCHES+=("$1")
      else
        echo "FAIL ARG value_without_selector=$1"
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ ${#TASK_IDS[@]} -eq 0 ]]; then
  echo "FAIL ARG missing_task_ids"
  exit 2
fi
if [[ ${#BRANCHES[@]} -eq 0 ]]; then
  echo "FAIL ARG missing_branches"
  exit 2
fi

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "FAIL BASE_REF unresolved=$BASE_REF"
  exit 2
fi

TASK_SPEC_ROOT="$(discover_task_spec_root "$BASE_REF")" || {
  echo "FAIL TASK_SPEC_ROOT not_found_on_base=$BASE_REF"
  exit 2
}
echo "TASK_SPEC_ROOT=$TASK_SPEC_ROOT"

fail=0
for id in "${TASK_IDS[@]}"; do
  if [[ ! "$id" =~ ^TASK_[0-9]{3,}$ ]]; then
    echo "TASK_ID_CHECK FAIL $id invalid_format"
    fail=1
    continue
  fi
  hits="$(git grep -n -I --fixed-strings "$id" "$BASE_REF" -- "$TASK_SPEC_ROOT" || true)"
  if [[ -n "$hits" ]]; then
    count="$(printf '%s\n' "$hits" | wc -l | tr -d ' ')"
    echo "TASK_ID_CHECK FAIL $id hits=$count"
  else
    echo "TASK_ID_CHECK PASS $id hits=0"
  fi
  [[ -n "$hits" ]] && fail=1

done

for br in "${BRANCHES[@]}"; do
  query="$br"
  query="${query#origin/}"
  n="$(git ls-remote --heads origin "refs/heads/$query" | wc -l | tr -d ' ')"
  if [[ "$n" != "0" ]]; then
    echo "BRANCH_CHECK FAIL $br remote_hits=$n"
    fail=1
  else
    echo "BRANCH_CHECK PASS $br remote_hits=0"
  fi
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
exit 0
