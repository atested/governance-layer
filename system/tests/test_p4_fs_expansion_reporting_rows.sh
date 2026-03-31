#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_p4_fs_expansion_reporting_rows"
REPORT1="$TMP_BASE/report1.json"
REPORT2="$TMP_BASE/report2.json"
ROWS1="$TMP_BASE/rows1.txt"
ROWS2="$TMP_BASE/rows2.txt"

mkdir -p "$TMP_BASE"

extract_rows() {
  local report="$1"
  local out="$2"
  python3 - "$report" > "$out" <<'PY'
import json
import sys

cmds = {
    'bash system/tests/test_p4_fs_delete_nonexec_admissibility.sh',
    'bash system/tests/test_p4_fs_copy_admissibility.sh',
    'bash system/tests/test_p4_fs_move_dir_semantics.sh',
}
report = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [r for r in report.get('results', []) if r.get('cmd') in cmds]
rows.sort(key=lambda r: r.get('cmd', ''))
assert len(rows) == 3, rows
for row in rows:
    assert row.get('status') == 'PASS', row
    assert int(row.get('rc', -1)) == 0, row
    print(f"{row.get('id')}|{row.get('cmd')}|{row.get('status')}|{row.get('rc')}")
PY
}

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$REPORT1" >/dev/null
extract_rows "$REPORT1" "$ROWS1"

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$REPORT2" >/dev/null
extract_rows "$REPORT2" "$ROWS2"

S1="$(shasum -a 256 "$ROWS1" | awk '{print $1}')"
S2="$(shasum -a 256 "$ROWS2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

cat "$ROWS1"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
