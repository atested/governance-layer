#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mcp-ref-workflow-row.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

R1="$TMP_DIR/report1.json"
R2="$TMP_DIR/report2.json"
ROW1="$TMP_DIR/row1.json"
ROW2="$TMP_DIR/row2.json"
CMD="bash system/tests/test_mcp_reference_workflow_e2e.sh"

bash scripts/dev_phase2_regression.sh --report "$R1" >/dev/null
bash scripts/dev_phase2_regression.sh --report "$R2" >/dev/null

python3 - "$R1" "$ROW1" "$CMD" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
out_path = sys.argv[2]
cmd = sys.argv[3]
row = next((r for r in report.get('results', []) if r.get('cmd') == cmd), None)
if row is None:
    raise SystemExit('FAIL:MISSING_ROW')
if row.get('status') != 'PASS':
    raise SystemExit('FAIL:NOT_PASS')
if int(row.get('rc', 1)) != 0:
    raise SystemExit('FAIL:NONZERO_RC')
open(out_path, 'w', encoding='utf-8').write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
PY

python3 - "$R2" "$ROW2" "$CMD" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
out_path = sys.argv[2]
cmd = sys.argv[3]
row = next((r for r in report.get('results', []) if r.get('cmd') == cmd), None)
if row is None:
    raise SystemExit('FAIL:MISSING_ROW')
open(out_path, 'w', encoding='utf-8').write(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n')
PY

H1="$(shasum -a 256 "$ROW1" | awk '{print $1}')"
H2="$(shasum -a 256 "$ROW2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:ROW_NON_DETERMINISTIC"; exit 1; }

echo "MCP_REFERENCE_WORKFLOW_REPORTING_ROW=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
