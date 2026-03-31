#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_p4_fs_move_dir_semantics"
WORK_BASE="$TMP_BASE/workdata"

run_once() {
  rm -rf "$WORK_BASE"
  mkdir -p "$WORK_BASE/runtime" "$WORK_BASE/work/src_dir/sub" "$WORK_BASE/work/dst_parent"

  export GOV_CANONICAL_REPO_PATH="$ROOT"
  export GOV_RUNTIME_PATH="$WORK_BASE/runtime"

  printf 'dir-move\n' > "$WORK_BASE/work/src_dir/sub/a.txt"

  local src_dir="$WORK_BASE/work/src_dir"
  local dst_dir="$WORK_BASE/work/dst_parent/moved"
  local traversal_dst="$WORK_BASE/work/../escape"
  local hot_dst="$ROOT/system/scripts/release-gate.sh"

  local intent_allow="$WORK_BASE/intent_allow.json"
  local intent_trav="$WORK_BASE/intent_trav.json"
  local intent_hot="$WORK_BASE/intent_hot.json"

  cat > "$intent_allow" <<EOF
{"tool":"FS_MOVE","args":{"src_path":"$src_dir","dst_path":"$dst_dir","overwrite":false},"intent":{"goal":"move dir allowed","constraints":{"overwrite":false},"requested_action":"FS_MOVE","expected_outputs":[{"ref":"file:dst_path","value":"$dst_dir"}]}}
EOF
  cat > "$intent_trav" <<EOF
{"tool":"FS_MOVE","args":{"src_path":"$src_dir","dst_path":"$traversal_dst","overwrite":false},"intent":{"goal":"move traversal denied","constraints":{"overwrite":false},"requested_action":"FS_MOVE","expected_outputs":[{"ref":"file:dst_path","value":"$traversal_dst"}]}}
EOF
  cat > "$intent_hot" <<EOF
{"tool":"FS_MOVE","args":{"src_path":"$src_dir","dst_path":"$hot_dst","overwrite":false},"intent":{"goal":"move hot denied","constraints":{"overwrite":false},"requested_action":"FS_MOVE","expected_outputs":[{"ref":"file:dst_path","value":"$hot_dst"}]}}
EOF

  local out_allow="$WORK_BASE/out_allow.json"
  local out_trav="$WORK_BASE/out_trav.json"
  local out_hot="$WORK_BASE/out_hot.json"

  python3 "$ROOT/scripts/policy-eval.py" "$intent_allow" > "$out_allow"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_trav" > "$out_trav"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_hot" > "$out_hot"

  python3 - "$out_allow" "$out_trav" "$out_hot" <<'PY'
import json
import sys

def parse(path):
    obj = json.load(open(path, encoding='utf-8'))
    codes = [r.get('code', '') for r in obj.get('policy_reasons', []) if isinstance(r, dict)]
    return obj.get('policy_decision'), codes

allow_dec, allow_codes = parse(sys.argv[1])
trav_dec, trav_codes = parse(sys.argv[2])
hot_dec, hot_codes = parse(sys.argv[3])

assert allow_dec == 'ALLOW', (allow_dec, allow_codes)
assert trav_dec == 'DENY' and 'PATH_TRAVERSAL' in trav_codes, (trav_dec, trav_codes)
assert hot_dec == 'DENY' and 'TARGET_IS_HOT_FILE' in hot_codes, (hot_dec, hot_codes)

print('CASE=FS_MOVE_DIR_ALLOWED PASS')
print('CASE=FS_MOVE_DIR_TRAVERSAL_DENY PASS')
print('CASE=FS_MOVE_DIR_HOT_FILE_DENY PASS')
print('REASON_TOKEN_MOVE_DIR_TRAVERSAL=PATH_TRAVERSAL')
print('REASON_TOKEN_MOVE_DIR_HOT=TARGET_IS_HOT_FILE')
PY
}

if [[ "${1:-}" == "--single-run" ]]; then
  run_once
  exit 0
fi

mkdir -p "$TMP_BASE"
RUN1="$TMP_BASE/run1.txt"
RUN2="$TMP_BASE/run2.txt"
run_once > "$RUN1"
run_once > "$RUN2"

S1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
S2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

cat "$RUN1"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
