#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: scripts/dev_merge_window_simulator.sh --mseq <ID> --base <gitref> --branches <file> [--test-cmd <cmd> ...] [--out-dir <dir>] [--repo <dir>] [--emit-cecil-dispatch|--no-emit-cecil-dispatch] [--emit-manifest|--no-emit-manifest] [--run-release-gate]
USAGE
}

sanitize_stream() {
  sed -E \
    -e 's#/U[s]ers/[^[:space:]]+#<ABS_PATH>#g' \
    -e 's#/V[o]lumes/[^[:space:]]+#<ABS_PATH>#g'
}

sanitize_line() {
  printf '%s' "$1" | sanitize_stream
}

trim_log() {
  local f="$1"
  if [[ ! -s "$f" ]]; then
    echo "<empty>"
    return
  fi
  awk 'NR<=20{print; next}{buf[(NR-1)%20]=$0} END{if (NR>40) print "..."; start=(NR>20?NR-20:1); for(i=start;i<=NR;i++) if (buf[(i-1)%20] != "") print buf[(i-1)%20]}' "$f"
}

repo="$(pwd)"
out_dir="out/merge_windows"
mseq=""
base_ref=""
branches_file=""
emit_cecil_dispatch=1
emit_manifest=1
run_release_gate=0
declare -a test_cmds=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mseq)
      mseq="${2:-}"
      shift 2
      ;;
    --base)
      base_ref="${2:-}"
      shift 2
      ;;
    --branches)
      branches_file="${2:-}"
      shift 2
      ;;
    --test-cmd)
      test_cmds+=("${2:-}")
      shift 2
      ;;
    --out-dir)
      out_dir="${2:-}"
      shift 2
      ;;
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --emit-cecil-dispatch)
      emit_cecil_dispatch=1
      shift
      ;;
    --no-emit-cecil-dispatch)
      emit_cecil_dispatch=0
      shift
      ;;
    --emit-manifest)
      emit_manifest=1
      shift
      ;;
    --no-emit-manifest)
      emit_manifest=0
      shift
      ;;
    --run-release-gate)
      run_release_gate=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$mseq" || -z "$base_ref" || -z "$branches_file" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -d "$repo/.git" ]]; then
  echo "ERROR=INVALID_REPO"
  exit 1
fi

if [[ ! -f "$branches_file" ]]; then
  echo "ERROR=MISSING_BRANCH_LIST"
  exit 1
fi

if [[ $run_release_gate -eq 1 ]]; then
  test_cmds+=("GOV_PROFILE=dev bash system/scripts/release-gate.sh")
fi

cd "$repo"

status_ok="YES"
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  if [[ "$line" != "?? out/" ]]; then
    status_ok="NO"
    break
  fi
done < <(git status --porcelain)

base_sha="$(git rev-parse "$base_ref")"
sim_branch="sim/$mseq"
packet_dir="$out_dir/$mseq"
mkdir -p "$packet_dir"
stop_packet="$packet_dir/STOP_PACKET.txt"
completion_packet="$packet_dir/COMPLETION_PACKET.txt"
cecil_dispatch="$packet_dir/CECIL_DISPATCH.txt"
merge_set_json="$packet_dir/MERGE_SET.json"

branches=()
while IFS= read -r br || [[ -n "$br" ]]; do
  br="${br%%#*}"
  br="$(printf '%s' "$br" | awk '{$1=$1;print}')"
  [[ -n "$br" ]] && branches+=("$br")
done < "$branches_file"

if [[ "${#branches[@]}" -eq 0 ]]; then
  {
    echo "MSEQ=$mseq"
    echo "Stage=INPUT"
    echo "Stop Reason=EMPTY_BRANCH_LIST"
    echo "Details=No branch refs provided"
  } > "$stop_packet"
  sanitize_stream < "$stop_packet" > "$stop_packet.tmp" && mv "$stop_packet.tmp" "$stop_packet"
  exit 1
fi

write_stop() {
  local stage="$1"
  local reason="$2"
  local details="$3"
  {
    echo "MSEQ=$mseq"
    echo "Stage=$stage"
    echo "Stop Reason=$reason"
    echo "Details=$details"
  } > "$stop_packet"
  sanitize_stream < "$stop_packet" > "$stop_packet.tmp" && mv "$stop_packet.tmp" "$stop_packet"
}

hot_files=(
  "system/scripts/release-gate.sh"
  "system/scripts/validate-proof-bundle.sh"
  "system/scripts/codex-unattended.sh"
  "docs/dev/WORK_QUEUE.md"
  "docs/dev/ASSIGNMENTS.md"
)

resolve_file="$packet_dir/.resolved_branches.tmp"
: > "$resolve_file"
for br in "${branches[@]}"; do
  if ! head_sha="$(git rev-parse --verify "$br" 2>/dev/null)"; then
    write_stop "PREFLIGHT" "MISSING_BRANCH" "Branch ref not found: $br"
    exit 1
  fi
  printf '%s\t%s\n' "$br" "$head_sha" >> "$resolve_file"
done

if [[ "$status_ok" != "YES" ]]; then
  write_stop "BASELINE" "DIRTY_TREE" "Working tree must be clean or only ?? out/"
  exit 1
fi

git checkout -B "$sim_branch" "$base_ref" >/dev/null 2>&1

gates_file="$packet_dir/.gates.tmp"
: > "$gates_file"
echo "Baseline check PASS" >> "$gates_file"

declare -a merge_commits=()

for br in "${branches[@]}"; do
  diff_names="$(git diff --name-only "$base_ref...$br" | sort)"
  hot_hit="NO"
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    for hf in "${hot_files[@]}"; do
      if [[ "$f" == "$hf" ]]; then
        hot_hit="YES"
        break
      fi
    done
    [[ "$hot_hit" == "YES" ]] && break
  done <<< "$diff_names"

  if [[ "$hot_hit" == "YES" ]]; then
    echo "Hot-file scan $br FAIL" >> "$gates_file"
    write_stop "PREFLIGHT" "HOT_FILE_VIOLATION" "Branch $br touches protected files"
    exit 1
  fi
  echo "Hot-file scan $br PASS" >> "$gates_file"

  if ! GIT_AUTHOR_DATE="2000-01-01T00:00:00Z" GIT_COMMITTER_DATE="2000-01-01T00:00:00Z" \
      git merge --no-ff --no-edit "$br" >/dev/null 2>"$packet_dir/.merge.err"; then
    git merge --abort >/dev/null 2>&1 || true
    echo "Merge conflicts STOP" >> "$gates_file"
    write_stop "MERGE" "MERGE_CONFLICT" "Merge conflict while merging $br"
    exit 1
  fi

  merge_commits+=("$(git rev-parse HEAD)")
done

echo "Merge conflicts NONE" >> "$gates_file"

final_sha="$(git rev-parse HEAD)"

tests_file="$packet_dir/.tests.tmp"
: > "$tests_file"
if [[ "${#test_cmds[@]}" -eq 0 ]]; then
  echo "Tests NONE" >> "$tests_file"
else
  idx=0
  for cmd in "${test_cmds[@]}"; do
    idx=$((idx+1))
    out_file="$packet_dir/.test_${idx}.out"
    err_file="$packet_dir/.test_${idx}.err"
    set +e
    bash -lc "$cmd" >"$out_file" 2>"$err_file"
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      echo "Test[$idx] PASS rc=$rc cmd=$(sanitize_line "$cmd")" >> "$tests_file"
    else
      echo "Test[$idx] FAIL rc=$rc cmd=$(sanitize_line "$cmd")" >> "$tests_file"
      {
        echo "MERGE_WINDOW=$mseq"
        echo "BASE_REF=$base_ref"
        echo "BASE_SHA=$base_sha"
        echo "FINAL_SHA=$final_sha"
        echo "Stage=TEST"
        echo "Stop Reason=TEST_FAILURE"
        echo "Details=Command index $idx failed"
        echo "OUTPUT_HEAD_TAIL_BEGIN"
        trim_log "$out_file"
        trim_log "$err_file"
        echo "OUTPUT_HEAD_TAIL_END"
      } > "$stop_packet"
      sanitize_stream < "$stop_packet" > "$stop_packet.tmp" && mv "$stop_packet.tmp" "$stop_packet"
      exit 1
    fi
  done
fi

diffstat="$(git diff --stat "$base_ref..$final_sha")"
merge_set_csv="$(IFS=,; echo "${branches[*]}")"

{
  echo "MERGE_WINDOW=$mseq"
  echo "BASE_REF=$base_ref"
  echo "BASE_SHA=$base_sha"
  echo "FINAL_SHA=$final_sha"
  echo "MERGE_SET=$merge_set_csv"
  echo "COMMITS_BEGIN"
  for c in "${merge_commits[@]}"; do
    echo "$c"
  done
  echo "$final_sha"
  echo "COMMITS_END"
  echo "DIFFSTAT_BEGIN"
  if [[ -n "$diffstat" ]]; then
    printf '%s\n' "$diffstat"
  else
    echo "<empty>"
  fi
  echo "DIFFSTAT_END"
  echo "GATES_BEGIN"
  cat "$gates_file"
  cat "$tests_file"
  echo "GATES_END"
  echo "PUSH_STATUS=SIMULATION_ONLY"
} > "$completion_packet"

sanitize_stream < "$completion_packet" > "$completion_packet.tmp" && mv "$completion_packet.tmp" "$completion_packet"

if [[ $emit_cecil_dispatch -eq 1 ]]; then
  {
    echo "CECIL DISPATCH — MERGE WINDOW"
    echo "MSEQ: $mseq"
    echo "Canonical Repo: __GOV_CANONICAL_REPO_PATH__"
    echo "Baseline SHA: $base_sha"
    echo "Merge set:"
    for br in "${branches[@]}"; do
      echo "- $br"
    done
    echo "Verification commands:"
    if [[ "${#test_cmds[@]}" -eq 0 ]]; then
      echo "- NONE"
    else
      for cmd in "${test_cmds[@]}"; do
        echo "- $(sanitize_line "$cmd")"
      done
    fi
    echo "Push policy: SIMULATION_ONLY"
  } > "$cecil_dispatch"
  sanitize_stream < "$cecil_dispatch" > "$cecil_dispatch.tmp" && mv "$cecil_dispatch.tmp" "$cecil_dispatch"
fi

if [[ $emit_manifest -eq 1 ]]; then
  test_cmds_file="$packet_dir/.test_cmds.tmp"
  hot_files_file="$packet_dir/.hot_files.tmp"
  : > "$test_cmds_file"
  : > "$hot_files_file"
  for cmd in "${test_cmds[@]}"; do
    sanitize_line "$cmd" >> "$test_cmds_file"
    printf '\n' >> "$test_cmds_file"
  done
  for hf in "${hot_files[@]}"; do
    echo "$hf" >> "$hot_files_file"
  done

  python3 - "$merge_set_json" "$mseq" "$base_ref" "$base_sha" "$resolve_file" "$test_cmds_file" "$hot_files_file" <<'PY'
import json
import sys

out_path, mseq, base_ref, base_sha, resolve_file, test_cmds_file, hot_files_file = sys.argv[1:8]
branches = []
with open(resolve_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        ref, sha = line.split('\t', 1)
        branches.append({"ref": ref, "head_sha": sha})

def read_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [ln.strip() for ln in f if ln.strip()]

test_cmds = read_lines(test_cmds_file)
hot_files = read_lines(hot_files_file)

manifest = {
    "mseq": mseq,
    "base_ref": base_ref,
    "base_sha": base_sha,
    "branches": branches,
    "test_cmds": test_cmds,
    "hot_files": hot_files,
}

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, sort_keys=True, separators=(',', ':'))
    f.write('\n')
PY
fi

exit 0
