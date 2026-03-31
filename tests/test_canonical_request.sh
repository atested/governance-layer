#!/usr/bin/env bash
# test_canonical_request.sh — Verify canonical request binding and normalization snapshot.
#
# T-CANON-001: Two requests with identical semantics but different JSON byte encodings.
#   Expect: different request_hash, same normalized canonical_path + reason code.
#
# T-CANON-002: Two requests differing in max_bytes (one within limit, one exceeds).
#   Expect: different request_hash, different normalized_args.max_bytes, different decision.
#
# Both tests additionally verify:
#   - request_hash present and sha256:-prefixed
#   - normalized_args present
#   - verify-record.py passes on each record
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURES="$ROOT/tests/fixtures"

pass=0
fail=0

assert_contains () {
  local name="$1" json="$2" expect="$3"
  if echo "$json" | grep -q "$expect"; then
    echo "PASS: $name (contains $expect)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (missing $expect)"
    echo "$json"
    fail=$((fail+1))
  fi
}

assert_eq () {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (== $want)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_ne () {
  local name="$1" a="$2" b="$3"
  if [[ "$a" != "$b" ]]; then
    echo "PASS: $name (values differ as expected)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (expected values to differ but they are equal: $a)"
    fail=$((fail+1))
  fi
}

verify_hash () {
  local name="$1" json_file="$2"
  if "$VERIFY" "$json_file" >/dev/null 2>&1; then
    echo "PASS: $name (record_hash verified)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (record_hash verify failed)"
    "$VERIFY" "$json_file" || true
    fail=$((fail+1))
  fi
}

extract () {
  # Usage: extract <json_string> <jq-like key path>
  # Minimal extractor using python3 (no jq required).
  local json="$1" key="$2"
  echo "$json" | python3 -c "
import json,sys
r=json.load(sys.stdin)
keys='$key'.split('.')
v=r
for k in keys:
    v=v[k] if k else v
print(v)
"
}

mkdir -p "$ROOT/LOGS"

# ---------------------------------------------------------------------------
# T-CANON-001: Identical semantics, different JSON bytes
# 001a: pretty-printed, keys in "natural" order
# 001b: compact, keys in different order (same effective values)
# Both: FS_WRITE with overwrite mismatch → DENY RC-FS-OVERWRITE-DISALLOWED
# ---------------------------------------------------------------------------
echo "--- T-CANON-001: identical semantics, different byte encoding ---"

j1a="$("$EVAL" "$FIXTURES/canon_001a.json")"
j1b="$("$EVAL" "$FIXTURES/canon_001b.json")"
echo "$j1a" > "$ROOT/LOGS/t-canon-001a.record.json"
echo "$j1b" > "$ROOT/LOGS/t-canon-001b.record.json"

# Both must DENY for the same reason
assert_contains  "T-CANON-001a decision DENY"       "$j1a" '"policy_decision": "DENY"'
assert_contains  "T-CANON-001b decision DENY"       "$j1b" '"policy_decision": "DENY"'
assert_contains  "T-CANON-001a reason overwrite"    "$j1a" 'RC-FS-OVERWRITE-DISALLOWED'
assert_contains  "T-CANON-001b reason overwrite"    "$j1b" 'RC-FS-OVERWRITE-DISALLOWED'

# request_hash must differ (different bytes)
rh1a="$(extract "$j1a" "request_hash")"
rh1b="$(extract "$j1b" "request_hash")"
assert_ne  "T-CANON-001 request_hash differs"  "$rh1a"  "$rh1b"
assert_contains "T-CANON-001a request_hash sha256" "$j1a" '"request_hash": "sha256:'
assert_contains "T-CANON-001b request_hash sha256" "$j1b" '"request_hash": "sha256:'

# normalized canonical_path must be identical
cp1a="$(extract "$j1a" "normalized_args.canonical_path")"
cp1b="$(extract "$j1b" "normalized_args.canonical_path")"
assert_eq  "T-CANON-001 normalized_args.canonical_path same"  "$cp1a"  "$cp1b"

# normalized_args.overwrite_requested and overwrite_intent must match between both
ow_a="$(extract "$j1a" "normalized_args.overwrite_requested")"
ow_b="$(extract "$j1b" "normalized_args.overwrite_requested")"
assert_eq  "T-CANON-001 normalized overwrite_requested same"  "$ow_a"  "$ow_b"

verify_hash  "T-CANON-001a hash"  "$ROOT/LOGS/t-canon-001a.record.json"
verify_hash  "T-CANON-001b hash"  "$ROOT/LOGS/t-canon-001b.record.json"

echo
# ---------------------------------------------------------------------------
# T-CANON-002: Same path, different max_bytes — normalization diverges
# 002a: max_bytes=4096 (within hard limit 65536) → ALLOW
# 002b: max_bytes=99999 (exceeds hard limit)     → DENY RC-FS-MAX-BYTES-EXCEEDED
# ---------------------------------------------------------------------------
echo "--- T-CANON-002: same path, max_bytes normalization diverges ---"

j2a="$("$EVAL" "$FIXTURES/canon_002a.json")"
j2b="$("$EVAL" "$FIXTURES/canon_002b.json")"
echo "$j2a" > "$ROOT/LOGS/t-canon-002a.record.json"
echo "$j2b" > "$ROOT/LOGS/t-canon-002b.record.json"

assert_contains  "T-CANON-002a decision ALLOW"        "$j2a" '"policy_decision": "ALLOW"'
assert_contains  "T-CANON-002b decision DENY"         "$j2b" '"policy_decision": "DENY"'
assert_contains  "T-CANON-002b reason max_bytes"      "$j2b" 'RC-FS-MAX-BYTES-EXCEEDED'

# request_hash must differ
rh2a="$(extract "$j2a" "request_hash")"
rh2b="$(extract "$j2b" "request_hash")"
assert_ne  "T-CANON-002 request_hash differs"  "$rh2a"  "$rh2b"

# normalized_args.max_bytes must differ
mb2a="$(extract "$j2a" "normalized_args.max_bytes")"
mb2b="$(extract "$j2b" "normalized_args.max_bytes")"
assert_ne  "T-CANON-002 normalized max_bytes differs"  "$mb2a"  "$mb2b"
assert_eq  "T-CANON-002a normalized max_bytes is 4096"   "$mb2a"  "4096"
assert_eq  "T-CANON-002b normalized max_bytes is 99999"  "$mb2b"  "99999"

# canonical_path must be identical (same path, same normalization)
cp2a="$(extract "$j2a" "normalized_args.canonical_path")"
cp2b="$(extract "$j2b" "normalized_args.canonical_path")"
assert_eq  "T-CANON-002 normalized_args.canonical_path same"  "$cp2a"  "$cp2b"

verify_hash  "T-CANON-002a hash"  "$ROOT/LOGS/t-canon-002a.record.json"
verify_hash  "T-CANON-002b hash"  "$ROOT/LOGS/t-canon-002b.record.json"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
