#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task121-rc-matrix.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

canon_hash() {
  python3 - <<'PY' "$1"
import json, hashlib, sys
p = sys.argv[1]
doc = json.load(open(p, encoding='utf-8'))
for k in ["timestamp_utc","session_id","request_id","record_hash","signature","signing_key_id","prev_record_hash"]:
    doc.pop(k, None)
blob = json.dumps(doc, sort_keys=True, separators=(',',':')).encode('utf-8')
print(hashlib.sha256(blob).hexdigest())
PY
}

check_case() {
  local name="$1" fixture="$2" want_decision="$3" want_code="$4"
  local out1="$TMPDIR_LOCAL/${name}.run1.json"
  local out2="$TMPDIR_LOCAL/${name}.run2.json"

  python3 "$EVAL" "$ROOT/tests/fixtures/$fixture" > "$out1"
  python3 "$EVAL" "$ROOT/tests/fixtures/$fixture" > "$out2"

  local h1 h2
  h1="$(canon_hash "$out1")"
  h2="$(canon_hash "$out2")"
  echo "${name}_NORM_SHA256_RUN1=$h1"
  echo "${name}_NORM_SHA256_RUN2=$h2"
  [[ "$h1" == "$h2" ]] || { echo "FAIL: $name nondeterministic normalized output"; exit 1; }

  python3 - <<'PY' "$out1" "$want_decision" "$want_code" "$name"
import json, sys
path, want_decision, want_code, name = sys.argv[1:5]
d = json.load(open(path, encoding='utf-8'))
if d.get('policy_decision') != want_decision:
    raise SystemExit(f"FAIL: {name} decision {d.get('policy_decision')} != {want_decision}")
codes = [r.get('code') for r in d.get('policy_reasons', []) if isinstance(r, dict)]
if want_code != '-' and want_code not in codes:
    raise SystemExit(f"FAIL: {name} missing expected code {want_code}; got {codes}")
if want_code == '-' and codes:
    raise SystemExit(f"FAIL: {name} expected no reason codes; got {codes}")
print(f"PASS: {name} decision/code checks")
print(f"{name}_DECISION={d.get('policy_decision')}")
print(f"{name}_CODES={','.join(codes)}")
PY
}

echo "--- T-POLICY-RC-001: deterministic RC matrix for core FS intents ---"
check_case "FS_READ_NOT_A_FILE" "fs_read_not_a_file.json" "DENY" "RC-FS-NOT-A-FILE"
check_case "FS_LIST_NOT_A_DIRECTORY" "fs_list_not_a_directory.json" "DENY" "RC-FS-NOT-A-DIRECTORY"
check_case "FS_LIST_INCLUDE_HIDDEN_DISALLOWED" "fs_list_include_hidden_disallowed.json" "DENY" "RC-FS-INCLUDE-HIDDEN-DISALLOWED"
check_case "FS_WRITE_EXECUTABLE_DISALLOWED" "fs_write_executable_disallowed.json" "DENY" "RC-FS-EXECUTABLE-DISALLOWED"
check_case "FS_DELETE_RECURSIVE_DISALLOWED" "delete_deny_recursive.json" "DENY" "RC-FS-RECURSIVE-DISALLOWED"
check_case "FS_DELETE_PATH_DISALLOWED" "delete_deny_path.json" "DENY" "RC-FS-PATH-DISALLOWED"
check_case "FS_READ_ALLOW" "canon_002a.json" "ALLOW" "-"

echo "PASS: policy RC matrix regression complete"
