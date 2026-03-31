#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task178-meta-determinism.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
}

normalize_and_check() {
  local src="$1" out="$2"
  python3 - <<'PY' "$src" "$out"
import re, sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
lines = [ln.rstrip() for ln in src.splitlines()]
# Normalize tempdir names if they appear in nested test output.
norm = [re.sub(r'/tmp/task\d+[-_][^/ ]+', '/tmp/TMPDIR', ln) for ln in lines]
pathlib.Path(sys.argv[2]).write_text("\n".join(norm) + "\n", encoding='utf-8')
begins = [ln.split(':',1)[1] for ln in norm if ln.startswith('BEGIN:')]
ends = [ln.split(':',1)[1].split()[0] for ln in norm if ln.startswith('END:')]
expected = ['TASK165','TASK168','TASK169','TASK171','TASK172']
expected_twice = expected + expected
if begins != expected_twice:
    print(f"FAIL: BEGIN ordering mismatch: {begins}")
    raise SystemExit(1)
if ends != expected_twice:
    print(f"FAIL: END ordering mismatch: {ends}")
    raise SystemExit(1)
# rc value can legitimately vary over time as dependencies merge;
# enforce per-task stability within each run instead of fixed constants.
for task in expected:
    rows = [ln for ln in norm if ln.startswith(f'END:{task} rc=')]
    if len(rows) != 2:
        print(f"FAIL: expected two END markers for {task}, got {len(rows)}")
        raise SystemExit(1)
    rcs = {ln.split('rc=')[1] for ln in rows}
    if len(rcs) != 1:
        print(f"FAIL: nondeterministic rc for {task}: {sorted(rcs)}")
        raise SystemExit(1)
if norm.count('INFO: PROOF_BUNDLE_DIR not set (TASK170 optional in meta-runner)') != 2:
    print('FAIL: missing TASK170 optional marker')
    raise SystemExit(1)
completion_count = (
    norm.count('PASS: external packaging checks meta-runner complete')
    + norm.count('FAIL: external packaging checks meta-runner detected failing subchecks')
)
if completion_count != 2:
    print('FAIL: missing deterministic completion marker')
    raise SystemExit(1)
print('PASS: meta-runner ordering and rc markers stable')
PY
}

echo "--- T-EXTERNAL-PACKAGING-META-001: meta-runner deterministic ordering/rc output ---"
unset PROOF_BUNDLE_DIR || true
set +e
bash "$ROOT/tests/run_external_packaging_checks.sh" > "$TMPDIR_LOCAL/run1.out" 2>&1
RC1=$?
bash "$ROOT/tests/run_external_packaging_checks.sh" > "$TMPDIR_LOCAL/run2.out" 2>&1
RC2=$?
set -e
echo "META_RUNNER_SCRIPT_RC_RUN1=$RC1"
echo "META_RUNNER_SCRIPT_RC_RUN2=$RC2"
[[ "$RC1" -eq "$RC2" ]] || { echo "FAIL: meta-runner script rc differs across runs"; exit 1; }
[[ "$RC1" -eq 0 || "$RC1" -eq 1 ]] || { echo "FAIL: unexpected meta-runner script rc=$RC1"; exit 1; }

normalize_and_check "$TMPDIR_LOCAL/run1.out" "$TMPDIR_LOCAL/run1.norm"
normalize_and_check "$TMPDIR_LOCAL/run2.out" "$TMPDIR_LOCAL/run2.norm"

H1="$(sha256_file "$TMPDIR_LOCAL/run1.norm")"
H2="$(sha256_file "$TMPDIR_LOCAL/run2.norm")"
echo "META_RUNNER_NORM_SHA256_RUN1=$H1"
echo "META_RUNNER_NORM_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: normalized meta-runner output nondeterministic"; exit 1; }
echo "PASS: meta-runner normalized output deterministic across two runs"

echo "Summary: external packaging meta-runner determinism checks complete"
