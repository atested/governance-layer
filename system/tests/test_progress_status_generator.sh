#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/progress-status.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

CATALOG="$TMPDIR_LOCAL/catalog.json"
REPORT="$TMPDIR_LOCAL/report.json"
SNAP="$TMPDIR_LOCAL/snapshot.md"
DEPS="$TMPDIR_LOCAL/deps.md"
OUT1="$TMPDIR_LOCAL/status1.json"
OUT2="$TMPDIR_LOCAL/status2.json"

cat > "$CATALOG" <<'JSON'
{"entries":[{"id":"VCAT_OBJ2_00000001","objective":"PHASE2","title":"obj2"},{"id":"VCAT_OBJ3_00000002","objective":"PHASE2","title":"obj3"}],"catalog_version":"verification_catalog_v1","entry_count":2}
JSON
cat > "$REPORT" <<'JSON'
{"report_version":"phase2_report_v1","results":[{"id":"VCAT_OBJ2_00000001","status":"FAIL","cmd":"bash t1","rc":1,"notes":"X"},{"id":"VCAT_OBJ3_00000002","status":"SKIP","cmd":"bash t2","rc":0,"notes":"Y"}]}
JSON
cat > "$SNAP" <<'TXT'
snapshot
TXT
cat > "$DEPS" <<'TXT'
1) Obj2 dependency line
2) Obj3 dependency line
TXT

bash "$ROOT/scripts/dev_progress_status.sh" --catalog "$CATALOG" --report "$REPORT" --snapshot "$SNAP" --deps "$DEPS" --output "$OUT1" >/dev/null
bash "$ROOT/scripts/dev_progress_status.sh" --catalog "$CATALOG" --report "$REPORT" --snapshot "$SNAP" --deps "$DEPS" --output "$OUT2" >/dev/null

S1="$(shasum -a 256 "$OUT1" | awk '{print $1}')"
S2="$(shasum -a 256 "$OUT2" | awk '{print $1}')"
[[ "$S1" == "$S2" ]] || { echo "FAIL: status output nondeterministic"; exit 1; }

python3 - "$OUT1" <<'PY'
import json,sys
j=json.load(open(sys.argv[1], encoding='utf-8'))
assert j['status_version']=='progress_status_v1'
assert len(j['open_verifications'])==2
print('CASE=PROGRESS_STATUS_GENERATOR PASS')
PY

echo "RUN1_SHA256=$S1"
echo "RUN2_SHA256=$S2"
