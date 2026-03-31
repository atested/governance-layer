#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task189-bash-portability.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT
sha256_file(){ python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}
scan_once(){
  local out="$1"
  python3 - <<'PY' "$ROOT" > "$out"
import pathlib, re, subprocess, sys
root = pathlib.Path(sys.argv[1])
patterns = [
    ('mapfile', re.compile(r'\bmapfile\b')),
    ('readarray', re.compile(r'\breadarray\b')),
    ('declare-A', re.compile(r'\bdeclare\s+-A\b')),
]
cmd = ['git','-C',str(root),'ls-files','tests/*.sh','system/scripts/*.sh']
files = subprocess.check_output(cmd, text=True).splitlines()
files = sorted(f for f in files if f and f != 'tests/test_external_bash_portability_scan.sh')
print('--- T-BASH-PORTABILITY-001: tracked shell scripts avoid bash4-only features ---')
offenders = []
for rel in files:
    txt = (root / rel).read_text(encoding='utf-8', errors='replace').splitlines()
    for i, line in enumerate(txt, 1):
        for name, rx in patterns:
            if rx.search(line):
                offenders.append((rel, i, name, line.strip()))
if offenders:
    for rel, line_no, name, line in sorted(offenders):
        print(f'FAIL: bash4-only feature {name} at {rel}:{line_no}: {line}')
    raise SystemExit(1)
print('PASS: no bash4-only feature patterns found (mapfile/readarray/declare -A)')
print(f'SCANNED_FILES_COUNT={len(files)}')
PY
}
set +e
scan_once "$TMPDIR_LOCAL/run1.out"; rc1=$?
scan_once "$TMPDIR_LOCAL/run2.out"; rc2=$?
set -e
cat "$TMPDIR_LOCAL/run1.out"
cat "$TMPDIR_LOCAL/run2.out"
echo "RC_RUN1=$rc1"
echo "RC_RUN2=$rc2"
[[ "$rc1" -eq "$rc2" ]] || { echo 'FAIL: rc mismatch across runs'; exit 1; }
H1="$(sha256_file "$TMPDIR_LOCAL/run1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.out")"
echo "BASH_PORTABILITY_SHA256_RUN1=$H1"
echo "BASH_PORTABILITY_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo 'FAIL: portability scan output nondeterministic'; exit 1; }
echo 'PASS: bash portability scan output deterministic across two runs'
