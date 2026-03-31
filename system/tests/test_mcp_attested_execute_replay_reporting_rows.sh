#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mcp-attested-replay-rows.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

R1="$TMP_DIR/report1.json"
R2="$TMP_DIR/report2.json"
ROWS1="$TMP_DIR/rows1.json"
ROWS2="$TMP_DIR/rows2.json"

CMDS=(
  "bash system/tests/test_mcp_attested_execute_includes_replay_artifact.sh"
  "bash system/tests/test_mcp_attested_execute_replay_context_unknown.sh"
)

bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R1" >/dev/null
bash "$ROOT/scripts/dev_phase2_regression.sh" --report "$R2" >/dev/null

python3 - "$R1" "$ROWS1" "${CMDS[@]}" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding='utf-8'))
out_path = sys.argv[2]
cmds = sys.argv[3:]
rows = []
for cmd in cmds:
    row = next((r for r in report.get('results', []) if r.get('cmd') == cmd), None)
    if row is None:
        raise SystemExit(f'FAIL:MISSING_ROW:{cmd}')
    if row.get('status') != 'PASS':
        raise SystemExit(f'FAIL:NOT_PASS:{cmd}')
    if int(row.get('rc', 1)) != 0:
        raise SystemExit(f'FAIL:NONZERO_RC:{cmd}')
    rows.append(row)
rows.sort(key=lambda r: r['cmd'])
with open(out_path, 'w', encoding='utf-8') as fh:
    fh.write(json.dumps(rows, sort_keys=True, separators=(',', ':')) + '\n')
PY

python3 - "$R2" "$ROWS2" "${CMDS[@]}" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding='utf-8'))
out_path = sys.argv[2]
cmds = sys.argv[3:]
rows = []
for cmd in cmds:
    row = next((r for r in report.get('results', []) if r.get('cmd') == cmd), None)
    if row is None:
        raise SystemExit(f'FAIL:MISSING_ROW:{cmd}')
    rows.append(row)
rows.sort(key=lambda r: r['cmd'])
with open(out_path, 'w', encoding='utf-8') as fh:
    fh.write(json.dumps(rows, sort_keys=True, separators=(',', ':')) + '\n')
PY

H1="$(shasum -a 256 "$ROWS1" | awk '{print $1}')"
H2="$(shasum -a 256 "$ROWS2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:ROW_NON_DETERMINISTIC"; exit 1; }

echo "MCP_ATTESTED_EXECUTE_REPLAY_REPORTING_ROWS=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
