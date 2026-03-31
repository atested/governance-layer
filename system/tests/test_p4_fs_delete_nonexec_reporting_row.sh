#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$ROOT/out/test_p4_fs_delete_nonexec_reporting_row"
REPORT1="$TMP_BASE/report1.json"
REPORT2="$TMP_BASE/report2.json"
ROW1="$TMP_BASE/row1.txt"
ROW2="$TMP_BASE/row2.txt"

mkdir -p "$TMP_BASE"

extract_row() {
  local report="$1"
  local out="$2"
  python3 - "$report" > "$out" <<'PY'
import json
import sys

cmd = "bash system/tests/test_p4_fs_delete_nonexec_admissibility.sh"
report = json.load(open(sys.argv[1], encoding="utf-8"))
rows = [r for r in report.get("results", []) if r.get("cmd") == cmd]
assert len(rows) == 1, rows
row = rows[0]
assert row.get("status") == "PASS", row
assert int(row.get("rc", -1)) == 0, row
print(f"{row.get('id')}|{row.get('cmd')}|{row.get('status')}|{row.get('rc')}")
PY
}

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$REPORT1" >/dev/null
extract_row "$REPORT1" "$ROW1"

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$REPORT2" >/dev/null
extract_row "$REPORT2" "$ROW2"

S1="$(shasum -a 256 "$ROW1" | awk '{print $1}')"
S2="$(shasum -a 256 "$ROW2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

cat "$ROW1"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
