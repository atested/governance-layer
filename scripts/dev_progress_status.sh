#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: scripts/dev_progress_status.sh [--catalog <path>] [--report <path>] [--snapshot <path>] [--deps <path>] [--output <path>]
Generates deterministic progress status JSON from catalog + machine report + planning files.
USAGE
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CATALOG="$ROOT/system/planning/verification_catalog.v1.json"
REPORT="$ROOT/out/phase2_reports/latest/report.v1.json"
SNAPSHOT="$ROOT/out/progress_spine_proposal/COMPLETENESS_SNAPSHOT.md"
DEPS="$ROOT/out/progress_spine_proposal/DEPENDENCY_QUEUE.md"
OUTPUT="$ROOT/out/progress_status/latest/status.v1.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --catalog)
      CATALOG="$2"; shift 2 ;;
    --report)
      REPORT="$2"; shift 2 ;;
    --snapshot)
      SNAPSHOT="$2"; shift 2 ;;
    --deps)
      DEPS="$2"; shift 2 ;;
    --output)
      OUTPUT="$2"; shift 2 ;;
    *)
      echo "FAIL: unknown arg: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ ! -f "$REPORT" ]]; then
  echo "PROGRESS_STATUS_ERROR=MISSING_REPORT"
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"

python3 - "$CATALOG" "$REPORT" "$SNAPSHOT" "$DEPS" "$OUTPUT" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

catalog_path = pathlib.Path(sys.argv[1])
report_path = pathlib.Path(sys.argv[2])
snapshot_path = pathlib.Path(sys.argv[3])
deps_path = pathlib.Path(sys.argv[4])
out_path = pathlib.Path(sys.argv[5])

catalog = {}
if catalog_path.is_file():
    data = json.loads(catalog_path.read_text(encoding='utf-8'))
    for e in data.get('entries', []):
        catalog[e.get('id')] = {
            'objective': e.get('objective', 'UNKNOWN'),
            'title': e.get('title', ''),
        }

report = json.loads(report_path.read_text(encoding='utf-8'))
open_ids = sorted([r['id'] for r in report.get('results', []) if r.get('status') in {'FAIL', 'SKIP'}])

deps_lines = []
if deps_path.is_file():
    for line in deps_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if re.match(r'^\d+\)', line):
            deps_lines.append(line)

blocked = []
for oid in open_ids:
    obj = catalog.get(oid, {}).get('objective', 'UNKNOWN').lower()
    token = 'UNKNOWN'
    if 'phase2' in obj or 'obj2' in oid.lower():
        for d in deps_lines:
            if 'obj2' in d.lower():
                token = 'OBJ2_DEP'
                break
    elif 'obj3' in oid.lower():
        for d in deps_lines:
            if 'obj3' in d.lower():
                token = 'OBJ3_DEP'
                break
    elif 'regression' in oid.lower():
        for d in deps_lines:
            if 'regression' in d.lower():
                token = 'REGRESSION_DEP'
                break
    blocked.append({'id': oid, 'dependency_token': token})

snapshot_digest = 'MISSING'
if snapshot_path.is_file():
    snapshot_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

out = {
    'status_version': 'progress_status_v1',
    'open_verifications': open_ids,
    'blocked_by_dependencies': blocked,
    'completeness_snapshot_digest': snapshot_digest,
}
out_path.write_text(json.dumps(out, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
print(f"OPEN_COUNT={len(open_ids)}")
print(f"STATUS_PATH={out_path}")
PY

cat "$OUTPUT"
