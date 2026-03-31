#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task190-meta-order.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT
sha256_file(){ python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}
normalize(){ python3 - <<'PY' "$1"
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
s=re.sub(r'/tmp/[^\s]+' , '/tmp/<TMP>', s)
print(s, end='' if s.endswith('\n') else '\n')
PY
}
run1="$TMPDIR_LOCAL/run1.out"; run2="$TMPDIR_LOCAL/run2.out"
set +e
PROOF_BUNDLE_DIR='' bash "$ROOT/tests/run_external_packaging_checks.sh" >"$run1" 2>&1; rc1=$?
PROOF_BUNDLE_DIR='' bash "$ROOT/tests/run_external_packaging_checks.sh" >"$run2" 2>&1; rc2=$?
set -e
norm1="$TMPDIR_LOCAL/run1.norm"; norm2="$TMPDIR_LOCAL/run2.norm"
normalize "$run1" > "$norm1"
normalize "$run2" > "$norm2"
map1="$TMPDIR_LOCAL/markers1.txt"; map2="$TMPDIR_LOCAL/markers2.txt"
rg '^(BEGIN:|END:)' "$norm1" | sed -e 's/[[:space:]]\+$//' > "$map1" || true
rg '^(BEGIN:|END:)' "$norm2" | sed -e 's/[[:space:]]\+$//' > "$map2" || true
python3 - <<'PY' "$map1" "$map2" || { echo 'FAIL: BEGIN/END ordering differs across runs'; exit 1; }
import pathlib, sys
a = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
b = pathlib.Path(sys.argv[2]).read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
sys.exit(0 if a == b else 1)
PY
echo '--- T-EXTERNAL-PACKAGING-META-ORDER-001: meta-runner ordering/rc map deterministic ---'
echo "RC_RUN1=$rc1"
echo "RC_RUN2=$rc2"
[[ "$rc1" -eq "$rc2" ]] || { echo 'FAIL: meta-runner rc mismatch'; exit 1; }
echo 'PASS: meta-runner ordering and rc markers stable'
H1="$(sha256_file "$norm1")"; H2="$(sha256_file "$norm2")"
echo "META_RUNNER_ORDER_SHA256_RUN1=$H1"
echo "META_RUNNER_ORDER_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo 'FAIL: meta-runner normalized output nondeterministic'; exit 1; }
echo 'PASS: meta-runner normalized output deterministic across two runs'
echo 'Summary: external packaging meta-runner ordering regression checks complete'
