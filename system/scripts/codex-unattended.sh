#!/usr/bin/env bash
set -euo pipefail

# BASE_REF_SUPPORT (TASK_508)
BASE_REF="origin/main"


REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  echo "ERROR: Not in a git repository" >&2
  exit 1
fi
cd "$REPO_ROOT"

LOCAL_ONLY_STATUS_ALLOW_RE='^(\?\? \.codex/.*|\?\? \.codex/| M ops/CODEX_BATCH\.txt|\?\? ops/CODEX_BATCH\.txt|\?\? docs/dev/evidence/TASK_[0-9]{3}/COMPLETION_PACKET\.json| M docs/dev/evidence/TASK_[0-9]{3}/COMPLETION_PACKET\.json)$'

err() {
  echo "ERROR: $*" >&2
  exit 1
}

TMP_FILES_CREATED=()
cleanup_tmp_files() {
  local f
  for f in "${TMP_FILES_CREATED[@]:-}"; do
    [ -n "$f" ] || continue
    rm -f -- "$f" 2>/dev/null || true
  done
  TMP_FILES_CREATED=()
}
trap cleanup_tmp_files EXIT

safe_mktemp() {
  local prefix="$1"
  local tries="${2:-5}"
  local tmpdir="${TMPDIR:-/tmp}"
  local i candidate
  for i in $(seq 1 "$tries"); do
    candidate="${tmpdir}/${prefix}.$(date +%s).$$.${RANDOM}.${i}"
    if ( set -o noclobber; : > "$candidate" ) 2>/dev/null; then
      chmod 600 "$candidate" 2>/dev/null || true
      TMP_FILES_CREATED+=("$candidate")
      printf '%s\n' "$candidate"
      return 0
    fi
    sleep 0.05
  done
  echo "ERROR: mktemp failed after ${tries} retries for prefix ${prefix}" >&2
  return 1
}

require_task_id() {
  local task_id="$1"
  if [[ ! "$task_id" =~ ^TASK_[0-9]{3}$ ]]; then
    err "Invalid task id '$task_id' (expected TASK_###)"
  fi
}

validate_publish_branch_name() {
  local branch_name="$1"
  local task_re='^codex/TASK_[0-9]{3}__[0-9a-f]{7,}$'
  local ops_re='^codex/OPS_[A-Z0-9_]+__[0-9a-f]{7,}$'
  local feature_re='^codex/FEATURE_[A-Z0-9_]+__[0-9a-f]{7,}$'
  local queue_re='^codex/QUEUE_[A-Z0-9_]+__[0-9a-f]{7,}$'

  if [[ "$branch_name" =~ $task_re || "$branch_name" =~ $ops_re || "$branch_name" =~ $feature_re || "$branch_name" =~ $queue_re ]]; then
    echo "OK: BRANCH_NAME_GUARD name=${branch_name}"
    return 0
  fi

  if [ "${ALLOW_UNSUFFIXED:-0}" = "1" ]; then
    echo "WARN: UNSUFFIXED_BRANCH_OVERRIDE name=${branch_name}"
    return 0
  fi

  echo "STOP: UNSUFFIXED_BRANCH_REFUSED name=${branch_name}" >&2
  return 1
}

check_clean_tree_allow_local() {
  local porcelain remaining
  porcelain="$(git status --porcelain)"
  if [ -z "$porcelain" ]; then
    return 0
  fi

  remaining="$(printf '%s\n' "$porcelain" | grep -Ev "$LOCAL_ONLY_STATUS_ALLOW_RE" || true)"
  if [ -n "$remaining" ]; then
    echo "ERROR: Working tree not clean" >&2
    echo "Allowed local artifacts: untracked .codex/, and ops/CODEX_BATCH.txt (M or ??)" >&2
    echo "Found:" >&2
    printf '%s\n' "$remaining" >&2
    exit 1
  fi
}

check_git_lock_writable() {
  local git_dir lock
  git_dir="$(git rev-parse --git-dir)"
  lock="${git_dir}/index.lock"
  if [ -e "$lock" ]; then
    err "$lock already exists (another git process may be running)"
  fi
  : > "$lock" || err "Cannot create $lock"
  rm -f "$lock" || err "Cannot remove $lock"
}

check_dns_github() {
  local attempts=5
  local sleep_seconds=2
  local i out
  local last_err=""

  for i in $(seq 1 "$attempts"); do
    set +e
    out="$(
      python3 - <<'PY' 2>&1
import socket
host = "github.com"
try:
    print(socket.gethostbyname(host))
except Exception as e:
    print(str(e))
    raise SystemExit(1)
PY
    )"
    local rc=$?
    set -e

    if [ "$rc" -eq 0 ]; then
      echo "OK: DNS github.com -> $out (attempt $i/$attempts)"
      return 0
    fi

    last_err="$out"
    if [ "$i" -lt "$attempts" ]; then
      echo "WARN: DNS attempt $i/$attempts failed; retrying in ${sleep_seconds}s" >&2
      sleep "$sleep_seconds"
    fi
  done

  echo "ERROR: DNS gate failed after $attempts attempts" >&2
  if [ -n "$last_err" ]; then
    printf '%s\n' "$last_err" >&2
  fi
  scutil --dns | sed -n '1,160p' >&2 || true
  return 1
}

check_ssh_github() {
  local attempts=3
  local sleep_seconds=2
  local i out
  local last_err=""

  for i in $(seq 1 "$attempts"); do
    out="$(ssh -T git@github.com 2>&1 || true)"
    if printf '%s\n' "$out" | grep -q "successfully authenticated"; then
      echo "OK: SSH auth ok (attempt $i/$attempts)"
      return 0
    fi

    last_err="$out"
    if [ "$i" -lt "$attempts" ]; then
      echo "WARN: SSH attempt $i/$attempts failed; retrying in ${sleep_seconds}s" >&2
      sleep "$sleep_seconds"
    fi
  done

  echo "ERROR: SSH gate failed after $attempts attempts" >&2
  if [ -n "$last_err" ]; then
    printf '%s\n' "$last_err" >&2
  fi
  return 1
}

ensure_not_main_branch() {
  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$branch" = "main" ]; then
    err "Current branch is main; refusing unattended execution"
  fi
}

ensure_base_ref_visible() {
  if ! git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null; then
    err "Base ref not visible: ${BASE_REF}"
  fi
}

get_task_spec_path() {
  local task_id="$1"
  local matches=()
  while IFS= read -r p; do
    matches+=("$p")
  done < <(find docs/dev/tasks/ready -maxdepth 1 -type f -name "${task_id}__*.md" | sort)

  if [ "${#matches[@]}" -eq 0 ]; then
    err "No task spec found for $task_id under docs/dev/tasks/ready"
  fi
  if [ "${#matches[@]}" -gt 1 ]; then
    echo "ERROR: Multiple task specs found for $task_id:" >&2
    printf '%s\n' "${matches[@]}" >&2
    exit 1
  fi

  printf '%s\n' "${matches[0]}"
}

parse_allowed_files() {
  local spec_path="$1"
  python3 - "$spec_path" <<'PY'
import re
import sys
from pathlib import Path

spec_path = Path(sys.argv[1])
lines = spec_path.read_text(encoding="utf-8", errors="replace").splitlines()

in_section = False
bullet_list_started = False
patterns = []

def normalize_header(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^#+\s*", "", stripped)
    return stripped.rstrip(":").strip().lower()

for raw in lines:
    stripped = raw.strip()
    header = normalize_header(stripped)

    if header in {
        "allowed files",
        "files allowed to touch",
    }:
        in_section = True
        bullet_list_started = False
        continue

    if not in_section:
        continue

    if header.startswith("files forbidden to touch"):
        break

    if stripped.startswith("#"):
        break

    if stripped == "":
        if bullet_list_started:
            break
        continue

    if stripped.lower() == "everything else":
        continue

    if re.match(r"^\d+[.)]\s+", stripped):
        continue

    m = re.match(r"^[-*]\s+(.+?)\s*$", stripped)
    if m:
        candidate = m.group(1).strip()
        bullet_list_started = True
    else:
        candidate = stripped

    if candidate.startswith("`") and candidate.endswith("`") and len(candidate) >= 2:
        candidate = candidate[1:-1].strip()
    if candidate:
        patterns.append(candidate)

if not patterns:
    print(f"No Allowed Files entries parsed from {spec_path}", file=sys.stderr)
    sys.exit(2)

for p in patterns:
    print(p)
PY
}

collect_changed_files() {
  {
    git diff --name-only
    git diff --name-only --cached
    git status --porcelain | awk '/^\?\? /{print substr($0,4)}'
  } | awk 'NF{print}' | sort -u | grep -Ev '^(\.codex/|ops/CODEX_BATCH\.txt$|docs/dev/evidence/TASK_[0-9]{3}/COMPLETION_PACKET\.json$)' || true
}

emit_completion_packet() {
  local task_id="$1"
  local status="$2"
  local evidence_dir="docs/dev/evidence/${task_id}"
  local packet_path="${evidence_dir}/COMPLETION_PACKET.json"
  local tests_file="${evidence_dir}/TESTS.txt"
  local branch head_sha base_sha tmp_changed evidence_present wall_clock routing_decision

  branch="$(git rev-parse --abbrev-ref HEAD)"
  head_sha="$(git rev-parse HEAD)"
  base_sha="$(git merge-base HEAD "$BASE_REF")"
  evidence_present="false"
  if [ -d "$evidence_dir" ] && [ -f "$tests_file" ]; then
    evidence_present="true"
  fi

  tmp_changed="$(safe_mktemp codex_unattended_commit_changed)"
  git show --pretty='' --name-only HEAD | awk 'NF{print}' | sort -u > "$tmp_changed"

  wall_clock=""
  if [[ "${CODEX_RUN_START_EPOCH:-}" =~ ^[0-9]+$ ]]; then
    wall_clock="$(( $(date +%s) - CODEX_RUN_START_EPOCH ))"
  fi

  routing_decision="${CODEX_ROUTING_DECISION:-}"

  python3 - "$packet_path" "$task_id" "$branch" "$status" "$tmp_changed" "$evidence_dir" "$evidence_present" "$base_sha" "$head_sha" "$wall_clock" "$routing_decision" <<'PY'
import json
import sys
from pathlib import Path

packet_path = Path(sys.argv[1])
task_id = sys.argv[2]
branch = sys.argv[3]
status = sys.argv[4]
changed_file = Path(sys.argv[5])
evidence_path = sys.argv[6]
evidence_present = sys.argv[7].lower() == "true"
base_sha = sys.argv[8]
head_sha = sys.argv[9]
wall_clock = sys.argv[10]
routing_decision = sys.argv[11]

files_changed = [
    line.strip()
    for line in changed_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if line.strip()
]

payload = {
    "task_id": task_id,
    "branch": branch,
    "status": status,
    "files_changed": files_changed,
    "evidence_path": evidence_path,
    "evidence_present": evidence_present,
    "allowed_files_compliant": True,
    "forbidden_files_clean": True,
    "base_sha": base_sha,
    "head_sha": head_sha,
}

if wall_clock:
    payload["wall_clock_seconds"] = int(wall_clock)
if routing_decision:
    payload["routing_decision"] = routing_decision

packet_path.parent.mkdir(parents=True, exist_ok=True)
packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  rm -f "$tmp_changed"
  echo "completion-packet: OK ($packet_path)"
}

cmd_reception_check() {
  local task_id="$1"
  local mode="${2:-execute}"
  require_task_id "$task_id"

  case "$mode" in
    execute|investigate) ;;
    *) err "Unsupported reception-check mode: $mode" ;;
  esac

  check_clean_tree_allow_local
  ensure_not_main_branch
  ensure_base_ref_visible

  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if ! git merge-base --is-ancestor "$BASE_REF" HEAD; then
    err "Current branch ${branch} does not contain ${BASE_REF}"
  fi

  local spec
  spec="$(get_task_spec_path "$task_id")"
  [ -f "$spec" ] || err "Missing task spec: $spec"

  local tmp_allowed
  tmp_allowed="$(safe_mktemp codex_unattended_allowed)"
  parse_allowed_files "$spec" > "$tmp_allowed"
  if [ ! -s "$tmp_allowed" ]; then
    err "Allowed Files unresolved for $task_id"
  fi

  if [ "$mode" = "execute" ]; then
    local evidence_dir="docs/dev/evidence/${task_id}"
    local tests_file="${evidence_dir}/TESTS.txt"
    [ -d "$evidence_dir" ] || err "Missing evidence directory: $evidence_dir"
    [ -f "$tests_file" ] || err "Missing evidence file: $tests_file"
  fi

  rm -f "$tmp_allowed"
  echo "reception-check: OK ($task_id)"
}

check_forbidden_changed_files() {
  local changed_file="$1"
  python3 - "$changed_file" <<'PY'
import sys
from pathlib import Path

forbidden = {
    "docs/dev/ASSIGNMENTS.md",
    "docs/dev/WORK_QUEUE.md",
}

changed = [line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
hits = [p for p in changed if p in forbidden]
if hits:
    print("Forbidden file modifications detected:")
    for path in hits:
        print(path)
    sys.exit(1)
PY
}

check_changed_files_against_allowed() {
  local allowed_file="$1"
  local changed_file="$2"

  python3 - "$allowed_file" "$changed_file" <<'PY'
import fnmatch
import sys
from pathlib import Path

allowed = [line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
changed = [line.strip() for line in Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]

violations = []
for path in changed:
    ok = any(fnmatch.fnmatch(path, pat) for pat in allowed)
    if not ok:
        violations.append(path)

if violations:
    print("Allowed Files violations:")
    for v in violations:
        print(v)
    sys.exit(1)
PY
}

cmd_preflight() {
  check_clean_tree_allow_local
  check_git_lock_writable
  check_dns_github
  check_ssh_github
  ensure_not_main_branch
  echo "Preflight: OK"
}

cmd_begin_task() {
  local task_id="$1"
  require_task_id "$task_id"

  git fetch origin --prune

  local branch_base="origin/main"
  local branch="codex/${task_id}"
  local unique_count
  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    unique_count="$(git rev-list --count "origin/main..${branch}")"
    if [ "$unique_count" -gt 0 ]; then
      err "local ${branch} has unmerged commits; archive/rename it before begin-task can recreate"
    fi
    git switch -C "$branch" "$branch_base"
  else
    git switch -c "$branch" "$branch_base"
  fi

  if [ "$(git rev-list --count HEAD..origin/main)" -ne 0 ]; then
    err "Branch $branch does not contain origin/main"
  fi

  local spec
  spec="$(get_task_spec_path "$task_id")"
  local tmp_allowed
  tmp_allowed="$(safe_mktemp codex_unattended_allowed)"
  parse_allowed_files "$spec" > "$tmp_allowed"

  echo "Task spec: $spec"
  echo "Allowed Files:"
  cat "$tmp_allowed"
  rm -f "$tmp_allowed"
}

cmd_verify_task() {
  local task_id="$1"
  require_task_id "$task_id"

  local evidence_dir="docs/dev/evidence/${task_id}"
  local tests_file="${evidence_dir}/TESTS.txt"
  [ -d "$evidence_dir" ] || err "Missing evidence directory: $evidence_dir"
  [ -f "$tests_file" ] || err "Missing evidence file: $tests_file"

  local spec
  spec="$(get_task_spec_path "$task_id")"

  local tmp_allowed tmp_changed
  tmp_allowed="$(safe_mktemp codex_unattended_allowed)"
  tmp_changed="$(safe_mktemp codex_unattended_changed)"

  parse_allowed_files "$spec" > "$tmp_allowed"
  collect_changed_files > "$tmp_changed"

  if [ -s "$tmp_changed" ]; then
    check_forbidden_changed_files "$tmp_changed"
    check_changed_files_against_allowed "$tmp_allowed" "$tmp_changed"
  fi

  rm -f "$tmp_allowed" "$tmp_changed"
  echo "verify-task: OK ($task_id)"
}

cmd_finalize_task() {
  local task_id="$1"
  local message="$2"
  require_task_id "$task_id"

  case "$message" in
    "${task_id}:"*) ;;
    *) err "Commit message must start with '${task_id}:'" ;;
  esac

  cmd_verify_task "$task_id"

  git add -A
  if git diff --cached --quiet; then
    err "No staged changes to commit"
  fi

  git commit -m "$message"
  validate_publish_branch_name "codex/${task_id}" || return 1
  git push -u origin "codex/${task_id}"

  check_clean_tree_allow_local
  emit_completion_packet "$task_id" "published"
  check_clean_tree_allow_local
  echo "finalize-task: OK ($task_id)"
}

cmd_check_publish_branch_name() {
  local branch_name="${1:-}"
  [ -n "$branch_name" ] || err "check-publish-branch-name requires branch name"
  validate_publish_branch_name "$branch_name"
}

# EXECUTE_TASK_SUPPORT (TASK_508)
cmd_execute_task() {
  local task_id="${1:-}"
  if [[ -z "$task_id" ]]; then
    err "execute-task requires TASK_###"
  fi

  cmd_reception_check "$task_id" "execute"

  # Resolve spec path using existing helper if present
  local spec_path=""
  if command -v get_task_spec_path >/dev/null 2>&1; then
    spec_path="$(get_task_spec_path "$task_id")"
  else
    # Fallback: best-effort lookup in ready/
    spec_path="$(ls -1 docs/dev/tasks/ready 2>/dev/null | rg -n "^${task_id}__" | head -n1 | cut -d: -f2 || true)"
    if [[ -n "$spec_path" ]]; then
      spec_path="docs/dev/tasks/ready/$spec_path"
    fi
  fi

  if [[ -z "$spec_path" || ! -f "$spec_path" ]]; then
    err "No task spec found for $task_id under docs/dev/tasks/ready"
  fi

  # Evidence file contract
  local evidence_dir="docs/dev/evidence/$task_id"
  local tests_file="$evidence_dir/TESTS.txt"
  mkdir -p "$evidence_dir"
  if [[ ! -f "$tests_file" ]]; then
    err "Missing evidence file: $tests_file"
  fi

  # Executor command must be provided explicitly (fail-closed)
  if [[ -z "${CODEX_EXEC_CMD:-}" ]]; then
    err "CODEX_EXEC_CMD is not set. Set it to the command that runs Codex on a spec, e.g. CODEX_EXEC_CMD='codex <...>'"
  fi

  echo "EXECUTE: task_id=$task_id"
  echo "EXECUTE: spec_path=$spec_path"
  echo "EXECUTE: evidence=$tests_file"

  # OPS_PROCESS_DOC_LOADING (FAIL-CLOSED)
  # Load ops process doc and prepend to every Codex execution.
  local ops_process_doc="docs/dev/OPS_PROCESS__CHATGPT_CODEX_CECIL__v1.md"
  if [[ ! -f "$ops_process_doc" ]]; then
    err "Missing required ops process doc: $ops_process_doc"
  fi
  if [[ ! -r "$ops_process_doc" ]]; then
    err "Ops process doc not readable: $ops_process_doc"
  fi
  echo "EXECUTE: ops_process_doc=$ops_process_doc"

  # Fail-closed executor contract: execution must stay on the current task branch.
  local exec_spec_path="$spec_path"
  local exec_contract_spec
  exec_contract_spec="$(safe_mktemp codex_exec_contract.md)"
  {
    # Prepend ops process doc (mandatory preamble)
    cat "$ops_process_doc"
    echo ""
    echo "---"
    echo ""
    cat <<EOF
# EXECUTION CONTRACT (FAIL-CLOSED)

You are executing ${task_id} on the current task branch. You MUST NOT run branch-changing commands.

Forbidden commands (any form):
# FORBIDDEN_COMMANDS_LIST_BEGIN
- git switch
- git checkout
- git merge
- git cherry-pick
- git rebase
- git worktree
- system/scripts/codex-unattended.sh begin-task
# FORBIDDEN_COMMANDS_LIST_END

If you believe a branch change is necessary:
1. Append a brief explanation to ${tests_file} (with a \$ command line and [exit=1] marker).
2. Exit nonzero.
3. Do not switch branches.

Original task spec follows.

EOF
    cat "$spec_path"
  } > "$exec_contract_spec"
  exec_spec_path="$exec_contract_spec"

  # Wrap execution with evidence-run if available; otherwise write basic markers.
  if [[ -x system/scripts/evidence-run.sh ]]; then
    system/scripts/evidence-run.sh "$tests_file" -- bash -lc "${CODEX_EXEC_CMD} \"$exec_spec_path\""
  else
    echo '$ bash -lc "'"${CODEX_EXEC_CMD}"'" "'"$exec_spec_path"'"' >> "$tests_file"
    set +e
    bash -lc "${CODEX_EXEC_CMD} \"$exec_spec_path\""
    rc=$?
    set -e
    rm -f "$exec_contract_spec"
    echo "[exit=$rc]" >> "$tests_file"
    if [[ "$rc" -ne 0 ]]; then
      err "Executor failed with exit=$rc"
    fi
  fi
  rm -f "$exec_contract_spec"

  # Stage changes (task branch should only contain task-scoped edits)
  git add -A

  # Enforce that something changed, otherwise finalize will fail and we want a clearer error
  if git diff --cached --quiet; then
    err "No staged changes after execute-task. Either CODEX_EXEC_CMD did nothing, or allowlist prevented edits."
  fi

  echo "EXECUTE: staged changes present"
}


cmd_run_one() {
  local task_id="$1"
  shift || true

  local no_op=0
  local verify_only=0

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --no-op) no_op=1 ;;
      --verify-only) verify_only=1 ;;
      *) err "Unknown option for run-one: $1" ;;
    esac
    shift
  done

  if [ "$no_op" -eq 1 ] && [ "$verify_only" -eq 1 ]; then
    err "--no-op and --verify-only are mutually exclusive"
  fi

  export CODEX_RUN_START_EPOCH="${CODEX_RUN_START_EPOCH:-$(date +%s)}"

  if [ "$verify_only" -eq 1 ]; then
    cmd_verify_task "$task_id"
    return
  fi

  cmd_preflight
  cmd_begin_task "$task_id"

  # EXECUTE_TASK_WIRING_FIX (TASK_508)
  # Only execute in real mode (skip for --no-op and --verify-only)
  if [[ "$no_op" -eq 0 && "$verify_only" -eq 0 ]]; then
    cmd_execute_task "$task_id"
  fi

  if [ "$no_op" -eq 1 ]; then
    echo "run-one: no-op complete ($task_id)"
    return
  fi

  cmd_verify_task "$task_id"
  cmd_finalize_task "$task_id" "${task_id}: unattended run"
}

cmd_run_list() {
  [ "$#" -gt 0 ] || err "run-list requires at least one TASK_###"
  local task_id
  for task_id in "$@"; do
    cmd_run_one "$task_id"
  done
}

cmd_run_default_rc() {
  local n task_id
  for n in 062 063 064 065 066 067; do
    task_id="TASK_${n}"
    cmd_run_one "$task_id"
  done
}

usage() {
  cat <<'USAGE'
Usage:
  bash system/scripts/codex-unattended.sh preflight
  bash system/scripts/codex-unattended.sh begin-task TASK_###
  bash system/scripts/codex-unattended.sh reception-check TASK_### [execute|investigate]
  bash system/scripts/codex-unattended.sh verify-task TASK_###
  bash system/scripts/codex-unattended.sh finalize-task TASK_### "TASK_###: <title>"
  bash system/scripts/codex-unattended.sh check-publish-branch-name codex/TASK_###__deadbee
  bash system/scripts/codex-unattended.sh run-one TASK_### [--no-op] [--verify-only]
  bash system/scripts/codex-unattended.sh run-list TASK_### TASK_### ...
  bash system/scripts/codex-unattended.sh run-default-rc
USAGE
}

main() {
  [ "$#" -ge 1 ] || { usage; exit 1; }

  # Global options must be parsed before selecting the command.
  while [[ "${1:-}" == --* ]]; do
    case "$1" in
      --base-ref)
        BASE_REF="${2:-}"
        if [[ -z "$BASE_REF" ]]; then
          echo "ERROR: --base-ref requires a ref argument" >&2
          exit 2
        fi
        shift 2
        ;;
      --base-ref=*)
        BASE_REF="${1#*=}"
        shift 1
        ;;
      *)
        break
        ;;
    esac
  done

  [ "$#" -ge 1 ] || { usage; exit 1; }

  local cmd="$1"
  shift || true

  case "$cmd" in
    preflight)
      [ "$#" -eq 0 ] || err "preflight takes no arguments"
      cmd_preflight
      ;;
    begin-task)
      [ "$#" -eq 1 ] || err "begin-task requires TASK_###"
      cmd_begin_task "$1"
      ;;
    reception-check)
      [ "$#" -ge 1 ] && [ "$#" -le 2 ] || err "reception-check requires TASK_### and optional mode"
      cmd_reception_check "$1" "${2:-execute}"
      ;;
    verify-task)
      [ "$#" -eq 1 ] || err "verify-task requires TASK_###"
      cmd_verify_task "$1"
      ;;
    finalize-task)
      [ "$#" -eq 2 ] || err "finalize-task requires TASK_### and commit message"
      cmd_finalize_task "$1" "$2"
      ;;
    check-publish-branch-name)
      [ "$#" -eq 1 ] || err "check-publish-branch-name requires branch name"
      cmd_check_publish_branch_name "$1"
      ;;
  execute-task)
    cmd_execute_task "${1:-}"
    ;;
    run-one)
      [ "$#" -ge 1 ] || err "run-one requires TASK_###"
      local task_id="$1"
      shift || true
      cmd_run_one "$task_id" "$@"
      ;;
    run-list)
      cmd_run_list "$@"
      ;;
    run-default-rc)
      [ "$#" -eq 0 ] || err "run-default-rc takes no arguments"
      cmd_run_default_rc
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      err "Unknown command: $cmd"
      ;;
  esac
}

main "$@"
