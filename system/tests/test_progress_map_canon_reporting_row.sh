#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/progress-map-reporting-row.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

R1="$TMPDIR_LOCAL/report1.json"
R2="$TMPDIR_LOCAL/report2.json"
N1="$TMPDIR_LOCAL/norm1.txt"
N2="$TMPDIR_LOCAL/norm2.txt"

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R1" >/dev/null
bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R2" >/dev/null

python3 - "$R1" <<'PY' > "$N1"
import json,sys
cmd='bash system/tests/test_progress_map_canon_generation.sh'
rows=json.load(open(sys.argv[1], encoding='utf-8')).get('results', [])
row=next((r for r in rows if r.get('cmd')==cmd), None)
assert row is not None, 'missing progress map row'
assert row.get('status')=='PASS', f"expected PASS got {row.get('status')}"
assert row.get('rc')==0, f"expected rc=0 got {row.get('rc')}"
print('ROW=' + ' | '.join([row.get('id',''), row.get('cmd',''), row.get('status',''), str(row.get('rc',''))]))
PY

python3 - "$R2" <<'PY' > "$N2"
import json,sys
cmd='bash system/tests/test_progress_map_canon_generation.sh'
rows=json.load(open(sys.argv[1], encoding='utf-8')).get('results', [])
row=next((r for r in rows if r.get('cmd')==cmd), None)
assert row is not None, 'missing progress map row'
assert row.get('status')=='PASS', f"expected PASS got {row.get('status')}"
assert row.get('rc')==0, f"expected rc=0 got {row.get('rc')}"
print('ROW=' + ' | '.join([row.get('id',''), row.get('cmd',''), row.get('status',''), str(row.get('rc',''))]))
PY

H1="$(shasum -a 256 "$N1" | awk '{print $1}')"
H2="$(shasum -a 256 "$N2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

cat "$N1"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
