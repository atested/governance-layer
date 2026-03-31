#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
FIXTURES="$ROOT/tests/fixtures"
RUNTIME_DIR="$ROOT/out/rdd"
cd "$ROOT"

export GOV_CANONICAL_REPO_PATH="$ROOT"
export GOV_RUNTIME_PATH="$ROOT/out/runtime"

pass=0
fail=0
skip=0

pass_case () {
  local id="$1" msg="$2"
  echo "PASS: $id $msg"
  pass=$((pass+1))
}

fail_case () {
  local id="$1" msg="$2"
  echo "FAIL: $id $msg"
  fail=$((fail+1))
}

skip_case () {
  local id="$1" msg="$2"
  echo "SKIP: $id $msg"
  skip=$((skip+1))
}

json_get () {
  local file="$1" path="$2"
  python3 - <<'PY' "$file" "$path"
import json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
parts = sys.argv[2].split('.')
cur = obj
for p in parts:
    if p.isdigit():
        cur = cur[int(p)]
    else:
        cur = cur.get(p)
print(json.dumps(cur) if isinstance(cur, (dict, list)) else str(cur))
PY
}

mkdir -p "$RUNTIME_DIR" "$ROOT/LOGS"

# Shared files for FS_COPY tests
SRC_PATH="$RUNTIME_DIR/pass-undecided-src.txt"
DST_EXISTS_PATH="$RUNTIME_DIR/pass-undecided-dst.txt"
DST_ALLOW_PATH="$RUNTIME_DIR/pass-allow-dst.txt"
printf 'src-content\n' > "$SRC_PATH"
printf 'dst-existing\n' > "$DST_EXISTS_PATH"
rm -f "$DST_ALLOW_PATH"

# --- UNDECIDED path using fixture ---
UNDECIDED_JSON="$ROOT/LOGS/t-undecided-001.record.json"
python3 "$EVAL" "$FIXTURES/fs_copy_dest_exists_undecided.json" > "$UNDECIDED_JSON"

[[ "$(json_get "$UNDECIDED_JSON" "policy_decision")" == "UNDECIDED" ]] \
  && pass_case "T-UNDECIDED-001" "policy_decision=UNDECIDED" \
  || fail_case "T-UNDECIDED-001" "expected UNDECIDED"

[[ "$(json_get "$UNDECIDED_JSON" "policy_reasons")" == "[]" ]] \
  && pass_case "T-UNDECIDED-002" "policy_reasons empty" \
  || fail_case "T-UNDECIDED-002" "expected []"

[[ "$(json_get "$UNDECIDED_JSON" "insufficiency.trigger")" == "dest_exists_no_overwrite" ]] \
  && pass_case "T-UNDECIDED-003" "insufficiency.trigger" \
  || fail_case "T-UNDECIDED-003" "unexpected insufficiency.trigger"

[[ "$(json_get "$UNDECIDED_JSON" "insufficiency.surface")" == "filesystem" ]] \
  && pass_case "T-UNDECIDED-004" "insufficiency.surface" \
  || fail_case "T-UNDECIDED-004" "unexpected insufficiency.surface"

[[ "$(json_get "$UNDECIDED_JSON" "insufficiency.tool")" == "FS_COPY" ]] \
  && pass_case "T-UNDECIDED-005" "insufficiency.tool" \
  || fail_case "T-UNDECIDED-005" "unexpected insufficiency.tool"

python3 - <<'PY' "$UNDECIDED_JSON"
import json, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
if not isinstance(obj.get('insufficiency'), dict):
    raise SystemExit(1)
PY
if [[ "$?" -eq 0 ]]; then
  pass_case "T-UNDECIDED-006" "insufficiency present"
else
  fail_case "T-UNDECIDED-006" "insufficiency missing"
fi

[[ "$(json_get "$UNDECIDED_JSON" "record_type")" == "pass_decision" ]] \
  && pass_case "T-UNDECIDED-007" "record_type=pass_decision" \
  || fail_case "T-UNDECIDED-007" "unexpected record_type"

python3 - <<'PY' "$UNDECIDED_JSON"
import json, re, sys
obj = json.load(open(sys.argv[1], encoding='utf-8'))
if not re.fullmatch(r"[0-9a-f]{16}", str(obj.get('process_id', ''))):
    raise SystemExit(1)
PY
if [[ "$?" -eq 0 ]]; then
  pass_case "T-UNDECIDED-008" "process_id is 16-char hex"
else
  fail_case "T-UNDECIDED-008" "process_id format invalid"
fi

# --- Regression tests ---
# T-REG-001: FS_COPY dest does not exist => ALLOW
REG001_FIX="$RUNTIME_DIR/reg001_fs_copy_allow.json"
cat > "$REG001_FIX" <<JSON
{
  "tool": "FS_COPY",
  "args": {
    "src_path": "$SRC_PATH",
    "dst_path": "$DST_ALLOW_PATH",
    "overwrite": false
  },
  "intent": {
    "goal": "Copy to new destination",
    "constraints": {"overwrite": false},
    "requested_action": "FS_COPY",
    "inputs": [{"ref": "file:src_path", "value": "$SRC_PATH"}],
    "expected_outputs": [{"ref": "file:dst_path", "value": "$DST_ALLOW_PATH"}]
  }
}
JSON
REG001_JSON="$ROOT/LOGS/t-reg-001.record.json"
python3 "$EVAL" "$REG001_FIX" > "$REG001_JSON"
[[ "$(json_get "$REG001_JSON" "policy_decision")" == "ALLOW" ]] \
  && pass_case "T-REG-001" "FS_COPY new destination ALLOW" \
  || fail_case "T-REG-001" "expected ALLOW"

# T-REG-002: skip if overwrite_allowed true path unavailable without forbidden edits
skip_case "T-REG-002" "Cannot produce FS_COPY overwrite=true ALLOW without changing capability registry or evaluator behavior; skipped per TASK_313 STOP guidance"

# T-REG-003: FS_COPY src outside allowed roots => DENY
REG003_FIX="$RUNTIME_DIR/reg003_fs_copy_src_outside.json"
cat > "$REG003_FIX" <<JSON
{
  "tool": "FS_COPY",
  "args": {
    "src_path": "/tmp/rdd-src-outside.txt",
    "dst_path": "$RUNTIME_DIR/reg003-dst.txt",
    "overwrite": false
  },
  "intent": {
    "goal": "Copy from outside allowed root",
    "constraints": {"overwrite": false},
    "requested_action": "FS_COPY",
    "inputs": [{"ref": "file:src_path", "value": "/tmp/rdd-src-outside.txt"}],
    "expected_outputs": [{"ref": "file:dst_path", "value": "$RUNTIME_DIR/reg003-dst.txt"}]
  }
}
JSON
REG003_JSON="$ROOT/LOGS/t-reg-003.record.json"
python3 "$EVAL" "$REG003_FIX" > "$REG003_JSON"
[[ "$(json_get "$REG003_JSON" "policy_decision")" == "DENY" ]] \
  && pass_case "T-REG-003" "FS_COPY src outside allowed root DENY" \
  || fail_case "T-REG-003" "expected DENY"

# T-REG-004: FS_COPY destination hot file => DENY
REG004_FIX="$RUNTIME_DIR/reg004_fs_copy_hotfile.json"
cat > "$REG004_FIX" <<JSON
{
  "tool": "FS_COPY",
  "args": {
    "src_path": "$SRC_PATH",
    "dst_path": "$ROOT/docs/dev/WORK_QUEUE.md",
    "overwrite": false
  },
  "intent": {
    "goal": "Copy to hot file",
    "constraints": {"overwrite": false},
    "requested_action": "FS_COPY",
    "inputs": [{"ref": "file:src_path", "value": "$SRC_PATH"}],
    "expected_outputs": [{"ref": "file:dst_path", "value": "$ROOT/docs/dev/WORK_QUEUE.md"}]
  }
}
JSON
REG004_JSON="$ROOT/LOGS/t-reg-004.record.json"
python3 "$EVAL" "$REG004_FIX" > "$REG004_JSON"
[[ "$(json_get "$REG004_JSON" "policy_decision")" == "DENY" ]] \
  && pass_case "T-REG-004" "FS_COPY hotfile destination DENY" \
  || fail_case "T-REG-004" "expected DENY"

# T-REG-005/T-REG-006: FS_WRITE allow case with new schema fields
REG005_FIX="$RUNTIME_DIR/reg005_fs_write_allow.json"
REG005_PATH="$RUNTIME_DIR/reg005-write.txt"
cat > "$REG005_FIX" <<JSON
{
  "tool": "FS_WRITE",
  "args": {
    "path": "$REG005_PATH",
    "content": "hello",
    "overwrite": false,
    "request_executable": false
  },
  "intent": {
    "goal": "Write regular file",
    "constraints": {"overwrite": false},
    "requested_action": "FS_WRITE",
    "inputs": [],
    "expected_outputs": [{"ref": "file:path", "value": "$REG005_PATH"}]
  }
}
JSON
REG005_JSON="$ROOT/LOGS/t-reg-005.record.json"
python3 "$EVAL" "$REG005_FIX" > "$REG005_JSON"
[[ "$(json_get "$REG005_JSON" "policy_decision")" == "ALLOW" && "$(json_get "$REG005_JSON" "record_type")" == "pass_decision" ]] \
  && pass_case "T-REG-005" "FS_WRITE allow with record_type" \
  || fail_case "T-REG-005" "expected ALLOW + pass_decision"

[[ "$(json_get "$REG005_JSON" "record_version")" == "0.2" ]] \
  && pass_case "T-REG-006" "FS_WRITE record_version=0.2" \
  || fail_case "T-REG-006" "expected record_version 0.2"

# T-REG-007: FS_MOVE destination outside allowed root => DENY
REG007_JSON="$ROOT/LOGS/t-reg-007.record.json"
python3 "$EVAL" "$FIXTURES/move_deny_dst_path.json" > "$REG007_JSON"
[[ "$(json_get "$REG007_JSON" "policy_decision")" == "DENY" ]] \
  && pass_case "T-REG-007" "FS_MOVE outside root DENY" \
  || fail_case "T-REG-007" "expected DENY"

echo "PASS: $pass  FAIL: $fail  SKIP: $skip"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
