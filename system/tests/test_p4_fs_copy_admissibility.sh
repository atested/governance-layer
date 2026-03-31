#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_p4_fs_copy_admissibility"
WORK_BASE="$TMP_BASE/workdata"

run_once() {
  rm -rf "$WORK_BASE"
  mkdir -p "$WORK_BASE/runtime" "$WORK_BASE/work/dir_src/sub" "$WORK_BASE/work/dir_dst"

  export GOV_CANONICAL_REPO_PATH="$ROOT"
  export GOV_RUNTIME_PATH="$WORK_BASE/runtime"

  local src_file="$WORK_BASE/work/src.txt"
  local dst_file="$WORK_BASE/work/dst.txt"
  printf 'copy-file\n' > "$src_file"

  printf 'copy-dir\n' > "$WORK_BASE/work/dir_src/sub/a.txt"

  local hot_dst="$ROOT/system/scripts/release-gate.sh"
  local traversal_dst="$WORK_BASE/work/../escape.txt"

  local intent_file_pass="$WORK_BASE/intent_file_pass.json"
  local intent_dir_pass="$WORK_BASE/intent_dir_pass.json"
  local intent_traversal="$WORK_BASE/intent_traversal.json"
  local intent_hot="$WORK_BASE/intent_hot.json"

  cat > "$intent_file_pass" <<EOF
{"tool":"FS_COPY","args":{"src_path":"$src_file","dst_path":"$dst_file","overwrite":false,"recursive":true},"intent":{"goal":"copy file","constraints":{"overwrite":false},"requested_action":"FS_COPY","expected_outputs":[{"ref":"file:dst_path","value":"$dst_file"}]}}
EOF
  cat > "$intent_dir_pass" <<EOF
{"tool":"FS_COPY","args":{"src_path":"$WORK_BASE/work/dir_src","dst_path":"$WORK_BASE/work/dir_dst/copied","overwrite":false,"recursive":true},"intent":{"goal":"copy dir","constraints":{"overwrite":false},"requested_action":"FS_COPY","expected_outputs":[{"ref":"file:dst_path","value":"$WORK_BASE/work/dir_dst/copied"}]}}
EOF
  cat > "$intent_traversal" <<EOF
{"tool":"FS_COPY","args":{"src_path":"$src_file","dst_path":"$traversal_dst","overwrite":false,"recursive":true},"intent":{"goal":"copy traversal deny","constraints":{"overwrite":false},"requested_action":"FS_COPY","expected_outputs":[{"ref":"file:dst_path","value":"$traversal_dst"}]}}
EOF
  cat > "$intent_hot" <<EOF
{"tool":"FS_COPY","args":{"src_path":"$src_file","dst_path":"$hot_dst","overwrite":false,"recursive":true},"intent":{"goal":"copy hot deny","constraints":{"overwrite":false},"requested_action":"FS_COPY","expected_outputs":[{"ref":"file:dst_path","value":"$hot_dst"}]}}
EOF

  local out_file_pass="$WORK_BASE/out_file_pass.json"
  local out_dir_pass="$WORK_BASE/out_dir_pass.json"
  local out_traversal="$WORK_BASE/out_traversal.json"
  local out_hot="$WORK_BASE/out_hot.json"

  python3 "$ROOT/scripts/policy-eval.py" "$intent_file_pass" > "$out_file_pass"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_dir_pass" > "$out_dir_pass"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_traversal" > "$out_traversal"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_hot" > "$out_hot"

  python3 - "$out_file_pass" "$out_dir_pass" "$out_traversal" "$out_hot" <<'PY'
import json
import sys

def parse(path):
    obj = json.load(open(path, encoding='utf-8'))
    codes = [r.get('code', '') for r in obj.get('policy_reasons', []) if isinstance(r, dict)]
    return obj.get('policy_decision'), codes

file_dec, file_codes = parse(sys.argv[1])
dir_dec, dir_codes = parse(sys.argv[2])
trav_dec, trav_codes = parse(sys.argv[3])
hot_dec, hot_codes = parse(sys.argv[4])

assert file_dec == 'ALLOW', (file_dec, file_codes)
assert dir_dec == 'ALLOW', (dir_dec, dir_codes)
assert trav_dec == 'DENY' and 'PATH_TRAVERSAL' in trav_codes, (trav_dec, trav_codes)
assert hot_dec == 'DENY' and 'TARGET_IS_HOT_FILE' in hot_codes, (hot_dec, hot_codes)

print('CASE=FS_COPY_FILE_ALLOWED PASS')
print('CASE=FS_COPY_DIR_ALLOWED PASS')
print('CASE=FS_COPY_TRAVERSAL_DENY PASS')
print('CASE=FS_COPY_HOT_FILE_DENY PASS')
print('REASON_TOKEN_COPY_TRAVERSAL=PATH_TRAVERSAL')
print('REASON_TOKEN_COPY_HOT=TARGET_IS_HOT_FILE')
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
