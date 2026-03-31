#!/usr/bin/env bash
set -euo pipefail

REPO="."
ALLOW_OUT="out/"
SALVAGE_PREFIX="origin/codex/SALVAGE_MAIN"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --allow-out) ALLOW_OUT="$2"; shift 2;;
    --salvage-prefix) SALVAGE_PREFIX="$2"; shift 2;;
    *) echo "baseline-gate: unknown arg: $1" >&2; exit 2;;
  esac
done

cd "$REPO"

STOP() {
  local code="$1"; shift
  {
    echo "STOP PACKET"
    echo "- Timestamp: $TIMESTAMP"
    echo "- Repo: $(pwd)"
    echo "- Step failed: baseline-gate"
    echo "- Reason: $*"
    echo "- Current HEAD: $(git rev-parse HEAD 2>/dev/null || echo "N/A")"
    echo "- origin/main: $(git rev-parse origin/main 2>/dev/null || echo "N/A")"
    echo "- git status --porcelain (verbatim):"
    echo
    git status --porcelain || true
    echo
  } >&2
  exit "$code"
}

require_git_repo() { [[ -d .git ]] || STOP 2 "not a git repo (missing .git)"; }

fetch_origin() {
  git fetch origin --prune >/dev/null 2>&1 || STOP 2 "git fetch origin --prune failed (origin unreachable or auth)"
}

ensure_main_checked_out() {
  git checkout -q main >/dev/null 2>&1 || STOP 2 "git checkout main failed"
}

porcelain_filtered_non_out() {
  git status --porcelain | awk -v allow="$ALLOW_OUT" '
    {
      if ($1 == "??") {
        if (index($2, allow) == 1) next
      }
      print
    }
  '
}

assert_clean_or_only_out() {
  local dirty
  dirty="$(porcelain_filtered_non_out)"
  [[ -z "$dirty" ]]
}

clean_untracked_except_out() {
  git clean -fdx -e "$ALLOW_OUT" >/dev/null 2>&1 || STOP 2 "git clean failed"
}

local_main_ahead_of_origin() {
  local ahead
  ahead="$(git log --oneline origin/main..main 2>/dev/null || true)"
  [[ -n "$ahead" ]]
}

salvage_local_main_commits() {
  local head short ref local_branch
  head="$(git rev-parse HEAD)"
  short="$(git rev-parse --short HEAD)"
  ref="${SALVAGE_PREFIX}_${short}__${short}"
  local_branch="codex/SALVAGE_MAIN_${short}__${short}"

  git branch -f "$local_branch" "$head" >/dev/null 2>&1 || STOP 2 "failed to create local salvage branch"
  git push -q origin "$local_branch:${ref#origin/}" >/dev/null 2>&1 || STOP 2 "failed to push salvage branch to origin ($ref)"

  {
    echo "INFO: salvage pushed"
    echo "- Salvage ref: $ref"
    echo "- Salvage head: $head"
  } >&2
}

ff_only_pull() {
  git pull --ff-only -q origin main >/dev/null 2>&1 || return 1
  return 0
}

hard_reset_to_origin_main() {
  git reset --hard -q origin/main >/dev/null 2>&1 || STOP 2 "git reset --hard origin/main failed"
}

main() {
  require_git_repo
  fetch_origin
  ensure_main_checked_out

  if ! ff_only_pull; then
    fetch_origin
    if local_main_ahead_of_origin; then
      salvage_local_main_commits
      hard_reset_to_origin_main
      fetch_origin
      ensure_main_checked_out
      ff_only_pull || STOP 4 "ff-only pull still failing after salvage+reset (ambiguous)"
    else
      STOP 4 "ff-only pull failed and main has no local-only commits to salvage (ambiguous divergence)"
    fi
  fi

  if ! assert_clean_or_only_out; then
    local dirty
    dirty="$(porcelain_filtered_non_out)"

    if echo "$dirty" | grep -qv '^?? '; then
      STOP 3 "tracked modifications present (refusing auto-reset)"
    fi

    clean_untracked_except_out
    assert_clean_or_only_out || STOP 2 "still dirty after cleaning untracked (unexpected)"
  fi

  echo "BASELINE_OK"
  echo "REPO=$(pwd)"
  echo "HEAD=$(git rev-parse HEAD)"
  echo "ORIGIN_MAIN=$(git rev-parse origin/main)"
  exit 0
}

main "$@"
