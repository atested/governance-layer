#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

git_out() {
  local out
  if ! out="$(git "$@" 2>&1)"; then
    echo "ERROR: git $* failed: $out" >&2
    exit 1
  fi
  printf '%s' "$out"
}

FETCH_OK=0
FETCH_ERR="informational mode: fetch skipped in status snapshot"

git_out fetch origin --prune >/dev/null
FETCH_OK=$?
if [ "$FETCH_OK" -ne 0 ]; then
  FETCH_ERR="fetch failed"
fi

python3 scripts/verify-ops-canonical.py >/dev/null || {
  echo "ERROR: verify-ops-canonical failed" >&2
  exit 1
}
bash system/scripts/inventory-snapshot.sh >/dev/null || {
  echo "ERROR: inventory snapshot failed" >&2
  exit 1
}

mkdir -p docs/dev/evidence/STATUS
mkdir -p docs/dev/evidence/QT

QUEUE_DRIFT_MODE="informational"
QUEUE_DRIFT_STATUS="present"
QUEUE_DRIFT_RC=0
QUEUE_DRIFT_OUT="docs/dev/evidence/STATUS/QUEUE_DRIFT_SCAN_LATEST.txt"
if [ -f system/scripts/queue-drift-scan.py ]; then
  if ! python3 system/scripts/queue-drift-scan.py >"$QUEUE_DRIFT_OUT" 2>&1; then
    QUEUE_DRIFT_RC=$?
    QUEUE_DRIFT_STATUS="error"
  fi
else
  QUEUE_DRIFT_STATUS="missing"
  QUEUE_DRIFT_RC=3
fi

LOCAL_MAIN="$(git_out rev-parse --short HEAD)"
ORIGIN_MAIN="$(git_out rev-parse --short origin/main)"
CLEAN="$(test -z "$(git status --porcelain)" && echo yes || echo no)"

READY_COUNT="$(ls -1 docs/dev/tasks/ready 2>/dev/null | wc -l | tr -d ' ')"
SEED_FILES_COUNT="$(find docs/dev/task-seeds -type f 2>/dev/null | wc -l | tr -d ' ')"
SEED_MD_PRESENT="$(test -f docs/dev/TASK_SEEDS.md && echo yes || echo no)"

CODEX_BATCH_CAP="${CODEX_BATCH_CAP:-4}"
CODEX_BATCH_CAP="$CODEX_BATCH_CAP" bash system/scripts/codex-batch.sh >/dev/null 2>&1 || true
BATCH_TASKS="$(grep -Eo 'TASK_[0-9]{3}' ops/CODEX_BATCH.txt 2>/dev/null | sort -u | tr '\n' ' ')"

REMOTE_TASK_BRANCHES_RAW="$(
  git_out for-each-ref \
    --sort=-committerdate \
    --format='%(refname:short)|%(objectname:short)|%(committerdate:iso8601)' \
    refs/remotes/origin/codex | grep -E '^origin/codex/TASK_[0-9]{3}\|' || true
)"
CODEX_BRANCHES="$(printf '%s\n' "$REMOTE_TASK_BRANCHES_RAW" | sed '/^$/d' | wc -l | tr -d ' ')"
TOP10_REMOTE_TASK_BRANCHES="$(printf '%s\n' "$REMOTE_TASK_BRANCHES_RAW" | head -10 | sed '/^$/d' | sed 's/^/  - /')"
if [ -z "${TOP10_REMOTE_TASK_BRANCHES:-}" ]; then
  TOP10_REMOTE_TASK_BRANCHES="  - <none>"
fi

MERGE_QUEUE_FILES_RAW="$(find docs/dev/merge-queue -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort || true)"
MERGE_QUEUE_COUNT="$(printf '%s\n' "$MERGE_QUEUE_FILES_RAW" | sed '/^$/d' | wc -l | tr -d ' ')"
MERGE_QUEUE_LIST="$(printf '%s\n' "$MERGE_QUEUE_FILES_RAW" | sed '/^$/d' | sed 's#^#  - #')"
if [ -z "${MERGE_QUEUE_LIST:-}" ]; then
  MERGE_QUEUE_LIST="  - <none>"
fi

RECENT_CODEX_BRANCHES_RAW="$(
  git_out for-each-ref \
    --sort=-committerdate \
    --format='%(refname:short)' \
    refs/remotes/origin/codex | head -50
)"
HOT_FILES=(
  "system/scripts/qt-runner.sh"
  "system/scripts/codex-unattended.sh"
  "system/scripts/codex-batch.sh"
  "scripts/task_scaffold.py"
)
HOT_DRIFT_REPORT=""
for hot_file in "${HOT_FILES[@]}"; do
  drift_count=0
  examples=""
  example_count=0
  while IFS= read -r branch_ref; do
    [ -n "$branch_ref" ] || continue
    diff_names="$(git_out diff --name-only origin/main...${branch_ref} -- "${hot_file}")"
    if [ -n "$diff_names" ]; then
      drift_count=$((drift_count + 1))
      if [ "$example_count" -lt 5 ]; then
        if [ -z "$examples" ]; then
          examples="$branch_ref"
        else
          examples="$examples, $branch_ref"
        fi
        example_count=$((example_count + 1))
      fi
    fi
  done <<EOF
$RECENT_CODEX_BRANCHES_RAW
EOF
  example_text="<none>"
  if [ -n "$examples" ]; then
    example_text="$examples"
  fi
  HOT_DRIFT_REPORT="${HOT_DRIFT_REPORT}
  - ${hot_file}: ${drift_count} branch(es) in top-50 codex refs; examples: ${example_text}"
done

QT_RUNS_COUNT="$(find docs/dev/evidence/QT -maxdepth 3 -type f -name 'TESTS.txt' 2>/dev/null | wc -l | tr -d ' ')"

RECENT_MERGES="$(git_out log --merges --oneline -n 10 || true)"
MERGES_7D="$(git_out log --since='7 days ago' --merges --oneline | wc -l | tr -d ' ')"
THROUGHPUT="$(python3 - <<PY
m=int("$MERGES_7D")
print(f"{m/7:.2f}")
PY
)"

DRIFT_WARN=""
if [ "$LOCAL_MAIN" != "$ORIGIN_MAIN" ]; then
  DRIFT_WARN="WARNING: local HEAD differs from origin/main"
fi

REPORT="$(cat <<EOF2
PROJECT STATUS
Repo:
  local head:  $LOCAL_MAIN
  origin/main: $ORIGIN_MAIN
  clean: $CLEAN
  $DRIFT_WARN
  fetch_ok: $FETCH_OK
  fetch_err: $FETCH_ERR

Work:
  ready tasks: $READY_COUNT
  seeds: TASK_SEEDS.md=$SEED_MD_PRESENT, seed files=$SEED_FILES_COUNT

Codex:
  batch cap: $CODEX_BATCH_CAP
  codex tasks in current batch: ${BATCH_TASKS:-<none>}
  remote codex task branches: $CODEX_BRANCHES
  top 10 most recently updated task branches:
$TOP10_REMOTE_TASK_BRANCHES

Merge Queue:
  artifacts (*.md): $MERGE_QUEUE_COUNT
$MERGE_QUEUE_LIST

Hot Script Drift (vs origin/main, top 50 recent origin/codex/* branches):
$HOT_DRIFT_REPORT

Qt:
  qt runs (TESTS.txt count): $QT_RUNS_COUNT
  qt evidence dir: docs/dev/evidence/QT

Queue drift scan:
  mode: $QUEUE_DRIFT_MODE
  status: $QUEUE_DRIFT_STATUS
  rc: $QUEUE_DRIFT_RC
  output: $QUEUE_DRIFT_OUT

Cecil:
  recent merges (last 10):
$(echo "$RECENT_MERGES" | sed 's/^/    /')

Forecast (low confidence):
  merges last 7d: $MERGES_7D  =>  $THROUGHPUT merges/day
EOF2
)"

echo "$REPORT" | tee docs/dev/evidence/STATUS/STATUS_LATEST.txt
