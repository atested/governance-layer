#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/phase2-report-p3-row.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

REPORT="$TMPDIR_LOCAL/report.json"

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$REPORT" >/dev/null

python3 - "$REPORT" <<'PY'
import json
import sys

cmd = 'bash system/tests/test_verify_attestation_bundle_signature_mode.sh'
rows = json.load(open(sys.argv[1], encoding='utf-8')).get('results', [])
row = None
for r in rows:
    if r.get('cmd') == cmd:
        row = r
        break
assert row is not None, 'missing p3 signature row'
assert row.get('status') == 'PASS', f"expected PASS got {row.get('status')}"
assert row.get('rc') == 0, f"expected rc=0 got {row.get('rc')}"
print('P3_ROW=' + ' | '.join([row.get('id',''), row.get('cmd',''), row.get('status',''), str(row.get('rc', ''))]))
print('CASE=PHASE2_REPORT_INCLUDES_P3_SIGNATURE_ROW PASS')
PY
