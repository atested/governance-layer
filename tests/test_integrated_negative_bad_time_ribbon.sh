#!/usr/bin/env bash
# Integrated E2E time ribbon checks:
# - Fail closed on missing required schema field (speculation_tag)
# - Render deterministically with stable ordering
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS="$ROOT/scripts/attest/integrated_e2e.py"
FIXTURES="$ROOT/tests/fixtures/integrated_e2e"

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

assert_eq () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "got:"
    printf '%s\n' "$got"
    echo "want:"
    printf '%s\n' "$want"
    fail=$((fail+1))
  fi
}

echo "--- T-TIMERIBBON-NEG-001: missing speculation_tag fails closed ---"
rc_bad=0
out_bad="$(python3 "$HARNESS" render-time-ribbon "$FIXTURES/time_ribbon_bad_missing_speculation_tag.json" 2>&1)" || rc_bad=$?
printf '%s\n' "$out_bad"
check_exit "T-TIMERIBBON-NEG-001 exit 2" "$rc_bad" "2"
assert_contains "T-TIMERIBBON-NEG-001 mentions speculation_tag" "$out_bad" "speculation_tag"

echo
echo "--- T-TIMERIBBON-DET-001: deterministic stable ordering ---"
out1="$(python3 "$HARNESS" render-time-ribbon "$FIXTURES/time_ribbon_unsorted.json")"
out2="$(python3 "$HARNESS" render-time-ribbon "$FIXTURES/time_ribbon_unsorted.json")"
assert_eq "T-TIMERIBBON-DET-001 repeat output identical" "$out1" "$out2"

expected=$'2026-02-23T10:00:01Z\trec-a\tspec-A\n2026-02-23T10:00:01Z\trec-c\tspec-C\n2026-02-23T10:00:02Z\trec-b\tspec-B'
assert_eq "T-TIMERIBBON-DET-001 exact sorted order" "$out1" "$expected"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
