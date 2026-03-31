#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
REPLAY="$ROOT/scripts/replay-record.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"

pass=0
fail=0

check_exit () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_eq () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  got : $got"
    echo "  want: $want"
    fail=$((fail+1))
  fi
}

assert_contains () {
  local name="$1" text="$2" expect="$3"
  if echo "$text" | grep -q "$expect"; then
    echo "PASS: $name (contains '$expect')"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing '$expect')"
    echo "$text"
    fail=$((fail+1))
  fi
}

extract_records_sha () {
  python3 - <<'PY' "$1"
import re, sys
text = sys.argv[1]
m = re.search(r"RECORDS_SHA=(sha256:[0-9a-f]{64})", text)
if not m:
    raise SystemExit(1)
print(m.group(1))
PY
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/gov-records-sha.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

RUN1="$TMP/run-one/deep/path/a"
RUN2="$TMP/run-two/other/location/b"
mkdir -p "$RUN1" "$RUN2"

echo "--- T-RECORDS-SHA-001: order/path-independent aggregate over stable record_hash values ---"

python3 "$EVAL" "$FIXTURES/canon_001a.json" > "$RUN1/deny.record.json"
python3 "$EVAL" "$FIXTURES/canon_002a.json" > "$RUN1/allow.record.json"

"$VERIFY" "$RUN1/deny.record.json" >/dev/null
"$VERIFY" "$RUN1/allow.record.json" >/dev/null

cp "$RUN1/deny.record.json" "$RUN2/copy-deny.record.json"
cp "$RUN1/allow.record.json" "$RUN2/copy-allow.record.json"

out_1="$(python3 "$REPLAY" "$RUN1/allow.record.json" "$RUN1/deny.record.json" 2>&1)"
rc_1=$?
check_exit "T-RECORDS-SHA-001 run1 replay bundle exit" "$rc_1" "0"
assert_contains "T-RECORDS-SHA-001 run1 emits RECORDS_SHA" "$out_1" "RECORDS_SHA="
sha_1="$(extract_records_sha "$out_1")"

out_2="$(python3 "$REPLAY" "$RUN2/copy-deny.record.json" "$RUN2/copy-allow.record.json" 2>&1)"
rc_2=$?
check_exit "T-RECORDS-SHA-001 run2 replay bundle exit" "$rc_2" "0"
assert_contains "T-RECORDS-SHA-001 run2 emits RECORDS_SHA" "$out_2" "RECORDS_SHA="
sha_2="$(extract_records_sha "$out_2")"

assert_eq "T-RECORDS-SHA-001 identical RECORDS_SHA across path+order changes" "$sha_1" "$sha_2"

echo "RECORDS_SHA run1: $sha_1"
echo "RECORDS_SHA run2: $sha_2"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
