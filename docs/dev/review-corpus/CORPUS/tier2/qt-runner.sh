#!/usr/bin/env bash
set -euo pipefail

err() {
  echo "ERROR: $*" >&2
  exit 1
}

RUN_START_EPOCH="$(date +%s)"
QT_USAGE_LEDGER_PATH="${QT_USAGE_LEDGER_PATH:-system/logs/qt-usage.jsonl}"

[ "$#" -eq 1 ] || err "Usage: $0 <job_file>"
JOB_FILE="$1"
[ -f "$JOB_FILE" ] || err "Job file not found: $JOB_FILE"

# Parse KEY: value header lines from markdown/yaml-like file.
parse_key() {
  local key="$1"
  awk -F': *' -v k="$key" '$1==k{print substr($0, index($0,":")+1); exit}' "$JOB_FILE" | sed 's/^ *//;s/ *$//'
}

JOB_ID="$(parse_key JOB_ID)"
JOB_TYPE="$(parse_key JOB_TYPE)"
TARGET_BRANCH="$(parse_key TARGET_BRANCH)"
TASK_ID="$(parse_key TASK_ID)"
TASK_SPEC="$(parse_key TASK_SPEC)"

[ -n "$JOB_ID" ] || err "Missing JOB_ID"
[ -n "$JOB_TYPE" ] || err "Missing JOB_TYPE"
[ -n "$TARGET_BRANCH" ] || err "Missing TARGET_BRANCH"
[ -n "$TASK_ID" ] || err "Missing TASK_ID"
[ -n "$TASK_SPEC" ] || err "Missing TASK_SPEC"

[ "$JOB_TYPE" = "merge_readiness" ] || err "Unsupported JOB_TYPE: $JOB_TYPE"

OUT_DIR="docs/dev/evidence/QT/${JOB_ID}"
TESTS_FILE="$OUT_DIR/TESTS.txt"
REPORT_FILE="$OUT_DIR/QT_REPORT.md"
mkdir -p "$OUT_DIR"

PASS=true
FAILURES=()

emit_qt_usage_event() {
  local status="$1"
  local end_epoch wall_clock
  end_epoch="$(date +%s)"
  wall_clock="$(( end_epoch - RUN_START_EPOCH ))"

  mkdir -p "$(dirname "$QT_USAGE_LEDGER_PATH")"
  python3 - "$QT_USAGE_LEDGER_PATH" "$TASK_ID" "$JOB_ID" "$JOB_TYPE" "$status" "$wall_clock" "$TARGET_BRANCH" "$REPORT_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ledger_path = Path(sys.argv[1])
task_id = sys.argv[2]
job_id = sys.argv[3]
job_type = sys.argv[4]
status = sys.argv[5]
wall_clock = int(sys.argv[6])
branch = sys.argv[7]
report_path = sys.argv[8]

payload = {
    "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "task_id": task_id,
    "qt_job_id": job_id,
    "qt_job_type": job_type,
    "status": status,
    "wall_clock_seconds": wall_clock,
}
if branch:
    payload["branch"] = branch
if report_path:
    payload["report_path"] = report_path

with ledger_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, sort_keys=True) + "\n")
PY
}

run_check() {
  local desc="$1"
  shift
  echo "\$ $*"
  if "$@"; then
    echo "[exit=0]"
  else
    local rc=$?
    echo "[exit=$rc]"
    PASS=false
    FAILURES+=("$desc")
  fi
  echo
}

# Resolve target branch ref.
TARGET_REF=""
if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
  TARGET_REF="refs/heads/${TARGET_BRANCH}"
elif git show-ref --verify --quiet "refs/remotes/origin/${TARGET_BRANCH}"; then
  TARGET_REF="refs/remotes/origin/${TARGET_BRANCH}"
else
  TARGET_REF="$TARGET_BRANCH"
fi

{
  echo "QT runner job: $JOB_ID"
  echo "Job type: $JOB_TYPE"
  echo "Target branch: $TARGET_BRANCH"
  echo "Task ID: $TASK_ID"
  echo "Task spec: $TASK_SPEC"
  echo

  run_check "target branch resolvable" git rev-parse --verify "$TARGET_REF"

  echo "\$ git show ${TARGET_REF}:${TASK_SPEC} | sed -n '1,120p'"
  SPEC_CONTENT="$(git show "${TARGET_REF}:${TASK_SPEC}" 2>/dev/null || true)"
  if [ -n "$SPEC_CONTENT" ]; then
    printf '%s\n' "$SPEC_CONTENT" | sed -n '1,120p'
    echo "[exit=0]"
  else
    echo "ERROR: cannot read task spec from target branch"
    echo "[exit=1]"
    PASS=false
    FAILURES+=("task spec missing on target branch")
  fi
  echo

  if [ -n "$SPEC_CONTENT" ]; then
    SPEC_TASK_ID="$(printf '%s\n' "$SPEC_CONTENT" | awk -F': *' '$1=="TASK_ID"{print $2; exit}')"
    echo "\$ check TASK_ID in spec equals ${TASK_ID}"
    if [ "$SPEC_TASK_ID" = "$TASK_ID" ]; then
      echo "TASK_ID match: $SPEC_TASK_ID"
      echo "[exit=0]"
    else
      echo "TASK_ID mismatch: found '$SPEC_TASK_ID'"
      echo "[exit=1]"
      PASS=false
      FAILURES+=("task id mismatch")
    fi
    echo
  fi

  EVIDENCE_PATH="docs/dev/evidence/${TASK_ID}/TESTS.txt"
  echo "\$ git cat-file -e ${TARGET_REF}:${EVIDENCE_PATH}"
  if git cat-file -e "${TARGET_REF}:${EVIDENCE_PATH}" 2>/dev/null; then
    echo "Evidence exists: ${EVIDENCE_PATH}"
    echo "[exit=0]"
  else
    echo "Missing evidence file: ${EVIDENCE_PATH}"
    echo "[exit=1]"
    PASS=false
    FAILURES+=("missing evidence file")
  fi
  echo

  echo "\$ git show ${TARGET_REF}:${EVIDENCE_PATH} | sed -n '1,200p'"
  EVIDENCE_CONTENT="$(git show "${TARGET_REF}:${EVIDENCE_PATH}" 2>/dev/null || true)"
  if [ -n "$EVIDENCE_CONTENT" ]; then
    printf '%s\n' "$EVIDENCE_CONTENT" | sed -n '1,200p'
    if printf '%s\n' "$EVIDENCE_CONTENT" | grep -q '^\$ ' && printf '%s\n' "$EVIDENCE_CONTENT" | grep -q '\[exit='; then
      echo "[exit=0]"
    else
      echo "Evidence missing command/exit markers"
      echo "[exit=1]"
      PASS=false
      FAILURES+=("evidence missing command markers")
    fi
  else
    echo "Evidence content empty or unreadable"
    echo "[exit=1]"
    PASS=false
    FAILURES+=("evidence unreadable")
  fi
  echo

  echo "\$ python3 - <<'PY'"
  python3 - "$TARGET_REF" "$TASK_SPEC" <<'PY'
import fnmatch
import re
import subprocess
import sys

ref = sys.argv[1]
spec_path = sys.argv[2]

spec = subprocess.check_output(["git", "show", f"{ref}:{spec_path}"], text=True, stderr=subprocess.DEVNULL)

# Parse allowlist in the same style as codex-unattended parser (plain lines or bullets).
in_section = False
allowed = []

def normalize_header(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^#+\s*", "", s)
    return s.rstrip(":").strip().lower()

for raw in spec.splitlines():
    stripped = raw.strip()
    hdr = normalize_header(stripped)
    if hdr in {"allowed files", "files allowed to touch"}:
        in_section = True
        continue
    if not in_section:
        continue
    if hdr == "files forbidden to touch":
        break
    if stripped.startswith("#"):
        break
    if not stripped or stripped.lower() == "everything else" or re.match(r"^\d+[.)]\s+", stripped):
        continue
    m = re.match(r"^[-*]\s+(.+?)\s*$", stripped)
    cand = m.group(1).strip() if m else stripped
    if cand.startswith("`") and cand.endswith("`") and len(cand) >= 2:
        cand = cand[1:-1].strip()
    if cand:
        allowed.append(cand)

if not allowed:
    print("FAIL: empty allowlist")
    raise SystemExit(2)

changed = subprocess.check_output(["git", "diff", "--name-only", f"origin/main...{ref}"], text=True)
changed_files = [x.strip() for x in changed.splitlines() if x.strip()]
violations = []
for p in changed_files:
    if p == "docs/dev/ASSIGNMENTS.md":
        violations.append(p)
        continue
    if not any(fnmatch.fnmatch(p, pat) for pat in allowed):
        violations.append(p)

print("Allowed patterns:")
for p in allowed:
    print(p)
print("Changed files:")
for c in changed_files:
    print(c)

if violations:
    print("Violations:")
    for v in violations:
        print(v)
    raise SystemExit(3)

print("PASS: changed files comply with allowlist")
PY
  rc=$?
  echo "[exit=$rc]"
  if [ "$rc" -ne 0 ]; then
    PASS=false
    FAILURES+=("allowed files compliance failed")
  fi
  echo

} > "$TESTS_FILE" 2>&1

{
  echo "# QT Report: ${JOB_ID}"
  echo
  echo "- Job type: ${JOB_TYPE}"
  echo "- Target branch: ${TARGET_BRANCH}"
  echo "- Task ID: ${TASK_ID}"
  echo "- Task spec: ${TASK_SPEC}"
  echo
  if [ "$PASS" = true ]; then
    echo "## Result"
    echo "PASS"
    echo
    echo "All merge-readiness checks passed."
  else
    echo "## Result"
    echo "FAIL"
    echo
    echo "Failed checks:"
    for f in "${FAILURES[@]}"; do
      echo "- $f"
    done
  fi
  echo
  echo "## Evidence"
  printf -- "- Raw log: \`%s\`\n" "$TESTS_FILE"
} > "$REPORT_FILE"

if [ "$PASS" = true ]; then
  emit_qt_usage_event "PASS"
  echo "qt-runner: PASS ($JOB_ID)"
  exit 0
fi

emit_qt_usage_event "FAIL"
echo "qt-runner: FAIL ($JOB_ID)" >&2
exit 1
