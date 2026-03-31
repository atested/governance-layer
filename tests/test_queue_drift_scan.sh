#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task118-queue-drift.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

echo "--- T-QUEUE-DRIFT-001: default scan deterministic output (rc=0) ---"
python3 "$ROOT/system/scripts/queue-drift-scan.py" > "$TMPDIR_LOCAL/default1.out"
python3 "$ROOT/system/scripts/queue-drift-scan.py" > "$TMPDIR_LOCAL/default2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/default1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/default2.out")"
echo "DEFAULT_SHA256_RUN1=$H1"
echo "DEFAULT_SHA256_RUN2=$H2"
[[ "$H1" == "$H2" ]] || { echo "FAIL: default scan output nondeterministic"; exit 1; }
echo "PASS: default scan output deterministic"

echo
if grep -qE '^- ' "$TMPDIR_LOCAL/default1.out"; then
  echo "--- T-QUEUE-DRIFT-002: --exit-on-drift returns rc=2 when drift present ---"
  set +e
  python3 "$ROOT/system/scripts/queue-drift-scan.py" --exit-on-drift > "$TMPDIR_LOCAL/drift1.out" 2>&1
  RC1=$?
  python3 "$ROOT/system/scripts/queue-drift-scan.py" --exit-on-drift > "$TMPDIR_LOCAL/drift2.out" 2>&1
  RC2=$?
  set -e
  echo "RC_EXIT_ON_DRIFT_RUN1=$RC1"
  echo "RC_EXIT_ON_DRIFT_RUN2=$RC2"
  [[ "$RC1" -eq 2 && "$RC2" -eq 2 ]] || { echo "FAIL: expected rc=2 with drift present"; exit 1; }
  H3="$(sha256_file "$TMPDIR_LOCAL/drift1.out")"
  H4="$(sha256_file "$TMPDIR_LOCAL/drift2.out")"
  echo "EXIT_ON_DRIFT_SHA256_RUN1=$H3"
  echo "EXIT_ON_DRIFT_SHA256_RUN2=$H4"
  [[ "$H3" == "$H4" ]] || { echo "FAIL: --exit-on-drift output nondeterministic"; exit 1; }
  echo "PASS: --exit-on-drift output deterministic when drift present"
else
  echo "INFO: no drift rows detected; asserting --exit-on-drift stays clean (rc=0)"
  python3 "$ROOT/system/scripts/queue-drift-scan.py" --exit-on-drift > "$TMPDIR_LOCAL/drift_clean1.out"
  python3 "$ROOT/system/scripts/queue-drift-scan.py" --exit-on-drift > "$TMPDIR_LOCAL/drift_clean2.out"
  H3="$(sha256_file "$TMPDIR_LOCAL/drift_clean1.out")"
  H4="$(sha256_file "$TMPDIR_LOCAL/drift_clean2.out")"
  echo "EXIT_ON_DRIFT_CLEAN_SHA256_RUN1=$H3"
  echo "EXIT_ON_DRIFT_CLEAN_SHA256_RUN2=$H4"
  [[ "$H3" == "$H4" ]] || { echo "FAIL: --exit-on-drift clean output nondeterministic"; exit 1; }
  echo "PASS: --exit-on-drift clean output deterministic"
fi

echo "PASS: queue drift scan regression checks complete"
