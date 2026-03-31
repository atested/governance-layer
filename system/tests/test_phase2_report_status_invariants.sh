#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/phase2-report-invariants.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

R1="$TMPDIR_LOCAL/report1.json"
R2="$TMPDIR_LOCAL/report2.json"

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R1" >/dev/null
bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R2" >/dev/null

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:nondeterministic_report"; exit 1; }

python3 - "$R1" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding='utf-8')).get('results', [])
assert rows, 'results empty'
for r in rows:
    status = r['status']
    rc = r['rc']
    skip_reason = r.get('skip_reason', '')
    if status == 'SKIP':
        assert rc != 0, f'SKIP with rc==0: {r["id"]}'
        assert skip_reason, f'SKIP missing skip_reason: {r["id"]}'
    elif status == 'PASS':
        assert rc == 0, f'PASS with rc!=0: {r["id"]}'
        assert skip_reason == '', f'PASS has skip_reason: {r["id"]}'
    elif status == 'FAIL':
        assert rc != 0, f'FAIL with rc==0: {r["id"]}'
        assert skip_reason == '', f'FAIL has skip_reason: {r["id"]}'
    else:
        raise AssertionError(f'unknown status: {status}')
print('CASE=PHASE2_REPORT_STATUS_INVARIANTS PASS')
PY

echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
