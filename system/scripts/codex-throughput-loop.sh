#!/usr/bin/env bash
set -euo pipefail

# High-throughput Codex batch loop (staged subcommands; fail-closed).
#
# This script intentionally avoids `run-one` to prevent the double-begin-task trap.
# Flow per task:
#   begin-task -> bootstrap evidence -> execute-task -> branch-lock guard ->
#   verify-task -> commit (if needed) -> safe publish
#
# Auto-fix classes implemented (per ops policy):
# - A: remove untracked base evidence dir for the task about to run
# - B: bootstrap missing docs/dev/evidence/TASK_###/TESTS.txt on task branch
# - C: avoid run-one entirely (staged subcommands)
# - D: executor nonzero with changes present -> salvage via verify/commit/publish
#
# Hard stops:
# - verify-task failure (except missing TESTS is auto-fixed before execute)
# - allowlist/spec mismatch
# - execute-task failed with no changes
# - branch changed during execute-task
# - any checkout/conflict failure
# - no force push (always safe publish to codex/TASK_###__<sha>)

BASE_REF="${BASE_REF:-codex/TASK_508}"
N="${N:-4}"
CODE_COUNT=0
EVIDENCE_COUNT=0
CURRENT_TASK=""
CLASS_BASE_REF="${CLASS_BASE_REF:-origin/main}"
EXEC_TIMEOUT="${EXEC_TIMEOUT:-900}"
EXEC_START_TIMEOUT="${EXEC_START_TIMEOUT:-5}"
SIMULATE_EXEC_STALL="${SIMULATE_EXEC_STALL:-0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMEOUT_WRAPPER="$ROOT/system/scripts/timeout_wrapper.py"
TIMEOUT_WRAPPER_RUN=""
NO_PUBLISH="${NO_PUBLISH:-0}"
TMP_DIR="${TMPDIR:-/tmp}"
TMP_CLEANUP_FILES=()
TMP_CLEANUP_GLOBS=(
  "codex_timeout_wrapper.*.py"
  "codex_throughput_tmp.*"
)

if [[ -z "${CODEX_EXEC_CMD:-}" ]]; then
  echo "ERROR: CODEX_EXEC_CMD is not set" >&2
  exit 2
fi

run_with_timeout() {
  local secs="$1"
  shift
  python3 "$TIMEOUT_WRAPPER_RUN" "$secs" "$CURRENT_TASK" "$@"
}

cleanup_known_temp_artifacts() {
  local scope="$1"
  local f
  local g
  for f in "${TMP_CLEANUP_FILES[@]:-}"; do
    [[ -n "$f" ]] || continue
    rm -f -- "$f" 2>/dev/null || true
  done
  TMP_CLEANUP_FILES=()
  for g in "${TMP_CLEANUP_GLOBS[@]}"; do
    find "$TMP_DIR" -maxdepth 1 -type f -name "$g" -print0 2>/dev/null | while IFS= read -r -d '' f; do
      rm -f -- "$f" 2>/dev/null || true
      echo "TRACE: cleaned stale temp artifact ($scope): $f"
    done
  done
}

safe_mktemp_file() {
  local prefix="$1"
  local suffix="$2"
  local tries="${3:-5}"
  local i
  local f
  for ((i=1; i<=tries; i++)); do
    f="$TMP_DIR/${prefix}.$(date +%s).$$.$RANDOM.$i${suffix}"
    if ( set -o noclobber; : > "$f" ) 2>/dev/null; then
      chmod 600 "$f" 2>/dev/null || true
      TMP_CLEANUP_FILES+=("$f")
      printf '%s\n' "$f"
      return 0
    fi
    sleep 0.05
  done
  echo "STOP: MKTEMP_FAIL prefix=${prefix} suffix=${suffix} tries=${tries}" >&2
  exit 2
}

classify_against_origin_main() {
  local classification="EVIDENCE_ONLY"
  while IFS= read -r changed; do
    if [[ -n "$changed" && "$changed" != docs/dev/evidence/* ]]; then
      classification="CODE"
      break
    fi
  done < <(git diff --name-only origin/main...HEAD)
  printf '%s\n' "$classification"
}

fix_base_untracked_evidence_dir() {
  local task_id="$1"
  local p
  p="docs/dev/evidence/${task_id}"

  git switch "$BASE_REF" >/dev/null
  if git status --porcelain | rg -q "^\\?\\? ${p}/$"; then
    echo "AUTO-FIX A: removing untracked base evidence dir $p"
    python3 - <<PY
import os, shutil
p = ${p@Q}
if os.path.isdir(p):
    shutil.rmtree(p)
PY
  fi
}

ensure_tests_evidence_on_task_branch() {
  local task_id="$1"
  local d
  local f
  d="docs/dev/evidence/${task_id}"
  f="${d}/TESTS.txt"
  mkdir -p "$d"
  if [[ ! -f "$f" ]]; then
    cat > "$f" <<EOF
$ echo "${task_id} evidence bootstrap (tests not run yet)"
[exit=0]
EOF
    return 0
  fi
  return 1
}

spec_path_for_task() {
  local task_id="$1"
  local spec
  spec="$(find docs/dev/tasks/ready -maxdepth 1 -type f -name "${task_id}__*.md" | sort | head -n1)"
  if [[ -z "$spec" ]]; then
    echo "ERROR: No spec found for $task_id under docs/dev/tasks/ready" >&2
    exit 2
  fi
  printf '%s\n' "$spec"
}

spec_blob_sha_for_ref() {
  local ref="$1"
  local spec_path="$2"
  git rev-parse "${ref}:${spec_path}" 2>/dev/null
}

sync_task_spec_from_base() {
  local task_id="$1"
  local spec_path="$2"
  local base_sha
  local task_sha

  base_sha="$(spec_blob_sha_for_ref "$BASE_REF" "$spec_path")"
  task_sha="$(spec_blob_sha_for_ref HEAD "$spec_path")"
  echo "TRACE: SPEC_SHA_BASE=${base_sha:-MISSING} SPEC_SHA_TASK=${task_sha:-MISSING} spec_path=${spec_path}"

  if [[ -z "${base_sha:-}" ]]; then
    echo "STOP: spec missing on BASE_REF for $task_id: $spec_path"
    exit 2
  fi
  if [[ -z "${task_sha:-}" ]]; then
    echo "STOP: spec missing on task branch for $task_id: $spec_path"
    exit 2
  fi
  if [[ "$base_sha" == "$task_sha" ]]; then
    return 0
  fi

  git show "${BASE_REF}:${spec_path}" > "${spec_path}"
  git add "$spec_path"
  git commit -m "${task_id}: sync READY spec from ${BASE_REF}" >/dev/null
  echo "TRACE: SPEC_SYNCED ${spec_path}"
}

apply_evidence_allowlist_patch() {
  local task_id="$1"
  local spec="$2"
  local current_branch
  current_branch="$(git --no-pager branch --show-current)"
  local stash_ref=""
  local evidence_status
  evidence_status="$(git status --porcelain docs/dev/evidence/${task_id}/TESTS.txt)"
  if [[ -n "$evidence_status" ]]; then
    git stash push -u -m "temp evidence ${task_id}" -- docs/dev/evidence/${task_id}/TESTS.txt >/dev/null
    stash_ref="$(git stash list --format='%gd' -n1)"
  fi
  git switch "$BASE_REF" >/dev/null
  local line
  line="- docs/dev/evidence/${task_id}/**"
  python3 - "$spec" "$line" <<'PY'
from pathlib import Path
import re
import sys

spec_path = Path(sys.argv[1])
line = sys.argv[2]
txt = spec_path.read_text(encoding="utf-8")
match = re.search(r'(?ms)(^##\s+Files allowed to touch\s*$\n)(.*?)(?=^##\s+|\Z)', txt)
if not match:
    raise SystemExit("ERROR: 'Files allowed to touch' section not found")
body = match.group(2)
if line.strip() in (ln.strip() for ln in body.splitlines()):
    sys.exit(0)
existing = body.rstrip()
if existing:
    new_body = existing + "\n" + line + "\n"
else:
    new_body = line + "\n"
out = txt[: match.start(2)] + new_body + txt[match.end(2) :]
spec_path.write_text(out, encoding="utf-8")
PY
  if git diff --quiet -- "$spec"; then
    git switch "$current_branch" >/dev/null
    return 1
  fi
  git add "$spec"
  git commit -m "${task_id}: allow evidence directory in Files allowed to touch" >/dev/null
  local commit_hash
  commit_hash="$(git rev-parse HEAD)"
  git switch "$current_branch" >/dev/null
  if [[ -n "$stash_ref" ]]; then
    git stash pop --quiet "$stash_ref" >/dev/null 2>&1 || true
  fi
  printf '%s\n' "$commit_hash"
  return 0
}

handle_allowlist_violation() {
  local task_id="$1"
  local output="$2"
  local spec="$3"
  local in_violation=0
  local paths=()
  while IFS= read -r line; do
    if [[ "$line" =~ ^Allowed[[:space:]]+Files[[:space:]]+violations: ]]; then
      in_violation=1
      continue
    fi
    if [[ $in_violation -eq 1 ]]; then
      if [[ -z "$line" ]]; then
        break
      fi
      if [[ "$line" =~ ^docs/dev/evidence/${task_id}/ ]]; then
        paths+=("$line")
        continue
      fi
      break
    fi
  done <<< "$output"

  if [[ ${#paths[@]} -eq 0 ]]; then
    return 1
  fi

  for path in "${paths[@]}"; do
    if [[ ! "$path" =~ ^docs/dev/evidence/${task_id}/ ]]; then
      return 1
    fi
  done

  local commit_hash
  if ! commit_hash="$(apply_evidence_allowlist_patch "$task_id" "$spec")"; then
    return 1
  fi
  echo "AUTO-FIX allowlist: added evidence dir for $task_id"
  git switch "codex/${task_id}" >/dev/null
  if ! git cherry-pick "$commit_hash" >/dev/null 2>&1; then
    echo "STOP: cherry-pick failed applying allowlist fix for $task_id"
    exit 2
  fi
  return 0
}

spec_has_branch_switch_evidence_commands() {
  local spec="$1"
  # Fail-closed guard for branch-changing commands in spec Procedure/Evidence sections.
  # Read-only evidence is required in batch mode.
  python3 - "$spec" <<'PY'
from pathlib import Path
import re, sys
spec = Path(sys.argv[1]).read_text(encoding="utf-8")
sections = []
for name in ("Procedure", "Test plan / evidence required", "Evidence required"):
    m = re.search(rf'(?ms)^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)', spec)
    if m:
        sections.append(m.group(1))
text = "\n".join(sections)
danger = re.compile(r'(?im)\b(begin-task|git\s+switch|git\s+checkout|git\s+cherry-pick|git\s+merge)\b')
sys.exit(0 if danger.search(text) else 1)
PY
}

select_tasks() {
  if [[ -n "${FORCE_TASK:-}" ]]; then
    echo "TRACE: FORCE_TASK bypassing selection"
    TASK_ARR=("$FORCE_TASK")
    return
  fi

  local candidates
  local task_id
  echo "TRACE: enumerating READY specs"
  candidates="$(
    ls -1 docs/dev/tasks/ready \
      | rg '^TASK_[0-9]+__' \
      | sed -E 's/^(TASK_[0-9]+)__.*/\1/' \
      | sort -t_ -k2,2n \
      | tail -r
  )"

  TASK_ARR=()
  echo "TRACE: filtering published branches"
  while IFS= read -r task_id; do
    [[ -z "$task_id" ]] && continue
    if git ls-remote --heads origin "codex/${task_id}__*" | rg -q .; then
      continue
    fi
    TASK_ARR+=("$task_id")
    [[ "${#TASK_ARR[@]}" -ge "$N" ]] && break
  done <<< "$candidates"
  echo "TRACE: selected ${#TASK_ARR[@]} tasks (${TASK_ARR[*]})"
}

run_task() {
  local task_id="$1"
  local stamp
  local rc
  local sha
  local spec_path
  local start_branch
  local end_branch

  echo
  echo "===================="
  echo "== RUN $task_id =="
  echo "===================="
  CURRENT_TASK="$task_id"

  git switch "$BASE_REF" >/dev/null
  fix_base_untracked_evidence_dir "$task_id"

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "STOP: base working tree not clean"
    git status --porcelain
    exit 2
  fi

  stamp="$(date +%Y%m%d_%H%M%S)"
  if git show-ref --verify --quiet "refs/heads/codex/${task_id}"; then
    git branch -m "codex/${task_id}" "archive/codex_${task_id}__${stamp}"
  fi

  # Auto-fix C: staged subcommands only (do not call run-one).
  echo "TRACE: fetching origin/main for $task_id"
  git fetch origin --prune >/dev/null 2>&1
  bash system/scripts/codex-unattended.sh --base-ref origin/main begin-task "$task_id"
  git switch "codex/${task_id}" >/dev/null

  # Auto-fix B: bootstrap missing TESTS.txt on task branch.
  if ensure_tests_evidence_on_task_branch "$task_id"; then
    echo "AUTO-FIX B: bootstrapping docs/dev/evidence/${task_id}/TESTS.txt"
    git add "docs/dev/evidence/${task_id}/TESTS.txt"
    git commit -m "${task_id}: bootstrap evidence TESTS.txt" >/dev/null
  fi

  # Evidence rule (fail-closed in batch mode): no branch-changing evidence commands.
  spec_path="$(spec_path_for_task "$task_id")"
  sync_task_spec_from_base "$task_id" "$spec_path"
  if spec_has_branch_switch_evidence_commands "$spec_path"; then
    {
      echo '$ echo "Branch-switching evidence commands are disallowed in batch mode; use read-only equivalents."'
      echo '[exit=0]'
    } >> "docs/dev/evidence/${task_id}/TESTS.txt"
    echo "STOP: spec requests branch-changing evidence commands for $task_id; replace with read-only equivalents"
    exit 2
  fi

  # Branch-lock guard around execute-task.
  start_branch="$(git --no-pager branch --show-current)"
  set +e
  if [[ "$SIMULATE_EXEC_STALL" == "1" ]]; then
    run_with_timeout "$EXEC_TIMEOUT" --startup-seconds "$EXEC_START_TIMEOUT" --startup-regex '^EXECUTE:' -- bash -lc 'sleep 30' </dev/null
  else
    run_with_timeout "$EXEC_TIMEOUT" --startup-seconds "$EXEC_START_TIMEOUT" --startup-regex '^EXECUTE:' -- bash system/scripts/codex-unattended.sh execute-task "$task_id" </dev/null
  fi
  rc=$?
  set -e
  end_branch="$(git --no-pager branch --show-current)"
  echo "EXECUTE_EXIT=$rc"

  if [[ "$end_branch" != "$start_branch" ]]; then
    echo "STOP: executor changed branches during ${task_id} (${start_branch} -> ${end_branch})."
    exit 2
  fi

  git switch "codex/${task_id}" >/dev/null

  if [[ "$rc" -ne 0 ]]; then
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "AUTO-FIX D: executor nonzero with changes present; salvaging"
    else
      echo "STOP: execute-task failed and produced no changes for $task_id"
      exit 2
    fi
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
  fi

  local verify_output
  local verify_rc
  local verify_rc2
  set +e
  verify_output="$(run_with_timeout 300 bash system/scripts/codex-unattended.sh verify-task "$task_id" </dev/null 2>&1)"
  verify_rc=$?
  set -e

  if [[ $verify_rc -ne 0 ]]; then
    if handle_allowlist_violation "$task_id" "$verify_output" "$spec_path"; then
      set +e
      run_with_timeout 300 bash system/scripts/codex-unattended.sh verify-task "$task_id" </dev/null
      verify_rc2=$?
      set -e
      if [[ $verify_rc2 -ne 0 ]]; then
        echo "STOP: verify-task failed for $task_id after allowlist fix"
        echo "$verify_output"
        exit 2
      fi
    else
      echo "$verify_output"
      echo "STOP: verify-task failed for $task_id"
      exit 2
    fi
  fi

  if ! git diff --cached --quiet; then
    git commit -m "${task_id}: implement" >/dev/null || true
  fi

  diff_class="$(classify_against_origin_main)"
  publish_class="$diff_class"
  if [[ "$publish_class" == "CODE" ]]; then
    ((CODE_COUNT++))
  else
    ((EVIDENCE_COUNT++))
  fi
  spec_allows_code=0
  if [[ -n "${spec_path:-}" && -f "${spec_path}" ]]; then
    if python3 - "$spec_path" <<'PY' | rg -q '^CODE_EXPECTED=1$'
from pathlib import Path
import re, sys

txt = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
m = re.search(r'(?ms)^##\s+Files allowed to touch\s*$\n(.*?)(?=^##\s+|\Z)', txt)
block = (m.group(1) if m else "").strip()
for ln in block.splitlines():
    ln = ln.strip()
    if not ln or ln == "[]":
        continue
    ln = re.sub(r'^-+\s*', '', ln)
    ln = ln.strip('"').strip("'").strip()
    if ln and not ln.startswith("docs/dev/evidence/"):
        print("CODE_EXPECTED=1")
        sys.exit(0)
print("CODE_EXPECTED=0")
sys.exit(0)
PY
    then
      spec_allows_code=1
    fi
  fi

  spec_expected="EVIDENCE_ONLY"
  if [[ "$spec_allows_code" -eq 1 ]]; then
    spec_expected="CODE"
  fi
  echo "TRACE_CLASS: task_id=${task_id} SPEC_EXPECTED=${spec_expected} DIFF_CLASS=${diff_class} PUBLISH_CLASS=${publish_class}"

  if [[ "$publish_class" == "EVIDENCE_ONLY" && "$spec_allows_code" -eq 1 ]]; then
    echo "STOP: ${task_id} produced EVIDENCE_ONLY changes but spec allowlist includes non-evidence paths; refusing to publish."
    exit 2
  fi
  sha="$(git rev-parse --short HEAD)"
  remote="origin/codex/${task_id}__${sha}"
  printf '%s  %s  %s\n' "$task_id" "$publish_class" "$remote"
  if [[ "$NO_PUBLISH" == "1" ]]; then
    echo "OK: NO_PUBLISH=1 skipping push for ${task_id}"
    git switch "$BASE_REF" >/dev/null
    return 0
  fi
  git push -u origin HEAD:"codex/${task_id}__${sha}" </dev/null
  PUBLISHED+=("origin/codex/${task_id}__${sha}")

  git switch "$BASE_REF" >/dev/null
}

main() {
  cleanup_known_temp_artifacts "start"
  if [[ ! -f "$TIMEOUT_WRAPPER" ]]; then
    echo "STOP: TIMEOUT_WRAPPER_NOT_FOUND path=$TIMEOUT_WRAPPER"
    exit 2
  fi
  TIMEOUT_WRAPPER_RUN="$(safe_mktemp_file "codex_timeout_wrapper" ".py")"
  cp "$TIMEOUT_WRAPPER" "$TIMEOUT_WRAPPER_RUN"
  chmod 700 "$TIMEOUT_WRAPPER_RUN"
  trap 'cleanup_known_temp_artifacts "exit"' EXIT

  git switch "$BASE_REF" >/dev/null
  echo "== Select newest $N READY tasks that are NOT already published as codex/TASK_###__* =="
  select_tasks
  if [[ "${#TASK_ARR[@]}" -eq 0 ]]; then
    echo "No unpublished READY tasks found."
    exit 0
  fi

  if [[ -n "${FORCE_TASK:-}" ]]; then
    TASK_ARR=("$FORCE_TASK")
    echo "FORCED TASK: $FORCE_TASK"
  else
    echo "TASKS:"
    printf '%s\n' "${TASK_ARR[@]}"
  fi

  PUBLISHED=()
  for t in "${TASK_ARR[@]}"; do
    run_task "$t"
  done

  if [[ "$NO_PUBLISH" != "1" ]]; then
    echo
    echo "== PUBLISHED REMOTE BRANCHES =="
    printf '%s\n' "${PUBLISHED[@]}"
  else
    echo
    echo "NO_PUBLISH=1"
  fi
  echo "CODE: $CODE_COUNT, EVIDENCE_ONLY: $EVIDENCE_COUNT"
}

main "$@"
