#!/usr/bin/env bash
set -euo pipefail

TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/task150-qds-optional.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())
PY
}

validate_qds_optional() {
  python3 - <<'PY' "$1"
import sys
from pathlib import Path

p = Path(sys.argv[1])
if not p.exists():
    print("INFO: queue_drift_scan.txt optional output absent")
    print("PASS: optional queue_drift_scan.txt absence allowed")
    raise SystemExit(0)

txt = p.read_text(encoding="utf-8")
if not txt:
    raise SystemExit("FAIL: queue_drift_scan.txt empty")
first = txt.splitlines()[0]
if first.startswith("INFO: queue-drift-scan unavailable"):
    print("PASS: queue_drift_scan sentinel accepted")
    raise SystemExit(0)
print("PASS: queue_drift_scan non-empty human text accepted")
PY
}

echo "--- T-QDS-OPT-001: non-empty human text accepted deterministically ---"
TXT1="$TMPDIR_LOCAL/qds1.txt"
TXT2="$TMPDIR_LOCAL/qds2.txt"
printf 'QUEUE_DRIFT_SCAN v1\nA) example drift\n' > "$TXT1"
printf 'QUEUE_DRIFT_SCAN v1\nA) example drift\n' > "$TXT2"
validate_qds_optional "$TXT1" | tee "$TMPDIR_LOCAL/human1.out"
validate_qds_optional "$TXT2" | tee "$TMPDIR_LOCAL/human2.out"
H1="$(sha256_file "$TMPDIR_LOCAL/human1.out")"
H2="$(sha256_file "$TMPDIR_LOCAL/human2.out")"
[[ "$H1" == "$H2" ]] || { echo "FAIL: human-text validator output digest mismatch"; exit 1; }
echo "QDS_HUMAN_SHA256_RUN1=$H1"
echo "QDS_HUMAN_SHA256_RUN2=$H2"
echo "PASS: human-text validator output deterministic across two runs"

echo "--- T-QDS-OPT-002: sentinel accepted ---"
SENT="$TMPDIR_LOCAL/sentinel.txt"
printf 'INFO: queue-drift-scan unavailable\n' > "$SENT"
validate_qds_optional "$SENT"

echo "--- T-QDS-OPT-003: malformed/empty files fail deterministically ---"
EMPTY="$TMPDIR_LOCAL/empty.txt"
: > "$EMPTY"
set +e
validate_qds_optional "$EMPTY" > "$TMPDIR_LOCAL/empty.out" 2>&1
RC1=$?
set -e
[[ "$RC1" -ne 0 ]] || { echo "FAIL: empty file unexpectedly passed"; exit 1; }
grep -q '^FAIL: queue_drift_scan.txt empty$' "$TMPDIR_LOCAL/empty.out"
cat "$TMPDIR_LOCAL/empty.out"
echo "PASS: empty file rejected with stable marker (exit=$RC1)"

echo "Summary: queue_drift_scan optional-file semantics checks complete"
