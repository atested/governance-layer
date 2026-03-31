#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_p4_fs_delete_nonexec_admissibility"
WORK_BASE="$TMP_BASE/workdata"

run_once() {
  rm -rf "$WORK_BASE"
  mkdir -p "$WORK_BASE/runtime" "$WORK_BASE/work"

  export GOV_CANONICAL_REPO_PATH="$ROOT"
  export GOV_RUNTIME_PATH="$WORK_BASE/runtime"

  local nonexec="$WORK_BASE/work/delete_me.txt"
  printf 'delete nonexec\n' > "$nonexec"
  chmod 644 "$nonexec"

  local execfile="$WORK_BASE/work/delete_me_exec.sh"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$execfile"
  chmod 755 "$execfile"

  local hot_path="$ROOT/system/scripts/release-gate.sh"
  local traversal="$WORK_BASE/work/../escape.txt"

  local intent_allow="$WORK_BASE/intent_allow.json"
  local intent_exec="$WORK_BASE/intent_exec.json"
  local intent_hot="$WORK_BASE/intent_hot.json"
  local intent_traversal="$WORK_BASE/intent_traversal.json"

  cat > "$intent_allow" <<EOF
{"tool":"FS_DELETE_NONEXEC","args":{"path":"$nonexec"},"intent":{"goal":"delete nonexec","constraints":{},"requested_action":"FS_DELETE_NONEXEC","expected_outputs":[{"ref":"file:path","value":"$nonexec"}]}}
EOF
  cat > "$intent_exec" <<EOF
{"tool":"FS_DELETE_NONEXEC","args":{"path":"$execfile"},"intent":{"goal":"reject executable","constraints":{},"requested_action":"FS_DELETE_NONEXEC","expected_outputs":[{"ref":"file:path","value":"$execfile"}]}}
EOF
  cat > "$intent_hot" <<EOF
{"tool":"FS_DELETE_NONEXEC","args":{"path":"$hot_path"},"intent":{"goal":"reject hot","constraints":{},"requested_action":"FS_DELETE_NONEXEC","expected_outputs":[{"ref":"file:path","value":"$hot_path"}]}}
EOF
  cat > "$intent_traversal" <<EOF
{"tool":"FS_DELETE_NONEXEC","args":{"path":"$traversal"},"intent":{"goal":"reject traversal","constraints":{},"requested_action":"FS_DELETE_NONEXEC","expected_outputs":[{"ref":"file:path","value":"$traversal"}]}}
EOF

  local out_allow="$WORK_BASE/out_allow.json"
  local out_exec="$WORK_BASE/out_exec.json"
  local out_hot="$WORK_BASE/out_hot.json"
  local out_traversal="$WORK_BASE/out_traversal.json"

  python3 "$ROOT/scripts/policy-eval.py" "$intent_allow" > "$out_allow"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_exec" > "$out_exec"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_hot" > "$out_hot"
  python3 "$ROOT/scripts/policy-eval.py" "$intent_traversal" > "$out_traversal"

  python3 - "$out_allow" "$out_exec" "$out_hot" "$out_traversal" <<'PY'
import json
import sys

def parse(path):
    obj = json.load(open(path, encoding="utf-8"))
    codes = [r.get("code", "") for r in obj.get("policy_reasons", []) if isinstance(r, dict)]
    return obj.get("policy_decision"), codes

def assert_has(codes, token):
    assert token in codes, (token, codes)

allow_decision, allow_codes = parse(sys.argv[1])
exec_decision, exec_codes = parse(sys.argv[2])
hot_decision, hot_codes = parse(sys.argv[3])
tr_decision, tr_codes = parse(sys.argv[4])

assert allow_decision == "ALLOW", (allow_decision, allow_codes)
assert exec_decision == "DENY", (exec_decision, exec_codes)
assert hot_decision == "DENY", (hot_decision, hot_codes)
assert tr_decision == "DENY", (tr_decision, tr_codes)

assert_has(exec_codes, "IS_EXECUTABLE")
assert_has(hot_codes, "TARGET_IS_HOT_FILE")
assert_has(tr_codes, "PATH_TRAVERSAL")

print("CASE=FS_DELETE_NONEXEC_ALLOWED PASS")
print("CASE=FS_DELETE_NONEXEC_IS_EXECUTABLE_DENY PASS")
print("CASE=FS_DELETE_NONEXEC_HOT_FILE_DENY PASS")
print("CASE=FS_DELETE_NONEXEC_TRAVERSAL_DENY PASS")
print("REASON_TOKEN_EXEC=IS_EXECUTABLE")
print("REASON_TOKEN_HOT=TARGET_IS_HOT_FILE")
print("REASON_TOKEN_TRAVERSAL=PATH_TRAVERSAL")
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
