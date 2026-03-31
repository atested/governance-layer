#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURE="$ROOT/tests/fixtures/fs_read_not_a_file.json"

pass=0
fail=0

check_exit() {
  local name="$1" got="$2" want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS: $name (exit=$got)"
    pass=$((pass+1))
  else
    echo "FAIL: $name (exit got=$got, want=$want)"
    fail=$((fail+1))
  fi
}

assert_contains() {
  local name="$1" file="$2" needle="$3"
  if grep -Fq "$needle" "$file"; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  expected to find: $needle"
    echo "  output:"
    sed 's/^/    /' "$file"
    fail=$((fail+1))
  fi
}

assert_files_equal() {
  local name="$1" a="$2" b="$3"
  if cmp -s "$a" "$b"; then
    echo "PASS: $name"
    pass=$((pass+1))
  else
    echo "FAIL: $name"
    echo "  files differ:"
    diff -u "$a" "$b" || true
    fail=$((fail+1))
  fi
}

run_capture() {
  local outfile="$1"
  shift
  set +e
  "$@" >"$outfile" 2>&1
  local rc=$?
  set -e
  return "$rc"
}

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/gov-verify-reason-order.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

echo "--- T-VERIFY-REASON-ORDER-001: canonical order passes ---"
python3 "$EVAL" "$FIXTURE" >"$tmpdir/good.json"

out="$tmpdir/good.out"
rc=0
run_capture "$out" python3 "$VERIFY" "$tmpdir/good.json" || rc=$?
check_exit "T-VERIFY-REASON-ORDER-001 canonical order verify-record" "$rc" "0"
assert_contains "T-VERIFY-REASON-ORDER-001 output" "$out" "PASS: record_hash verified"

echo
echo "--- T-VERIFY-REASON-ORDER-002: non-canonical order fails closed ---"
python3 - <<'PY' "$ROOT" "$tmpdir/good.json" "$tmpdir/bad-order.json"
import importlib.util
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = Path(sys.argv[2])
dst = Path(sys.argv[3])

verify_spec = importlib.util.spec_from_file_location("verify_record_impl", root / "scripts" / "verify-record.py")
verify_mod = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verify_mod)

rec = json.loads(src.read_text(encoding="utf-8"))
reasons = rec.get("policy_reasons", [])
if len(reasons) < 2:
    raise SystemExit("fixture must produce at least two policy reasons")

# Force a deterministic, self-consistent but non-canonical order.
rec["policy_reasons"] = [reasons[1], reasons[0], *reasons[2:]]
rec["record_hash"] = "sha256:" + verify_mod.sha256_hex(verify_mod.signing_preimage_payload(rec))
rec["signature"] = None
rec["signing_key_id"] = None

dst.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
PY

out1="$tmpdir/bad-1.out"
out2="$tmpdir/bad-2.out"
rc1=0
run_capture "$out1" python3 "$VERIFY" "$tmpdir/bad-order.json" || rc1=$?
rc2=0
run_capture "$out2" python3 "$VERIFY" "$tmpdir/bad-order.json" || rc2=$?

check_exit "T-VERIFY-REASON-ORDER-002 non-canonical order verify-record (run 1)" "$rc1" "1"
check_exit "T-VERIFY-REASON-ORDER-002 non-canonical order verify-record (run 2)" "$rc2" "1"
assert_contains "T-VERIFY-REASON-ORDER-002 mismatch message" "$out1" "FAIL: policy_reasons reason_code order mismatch (expected REASON_ORDER)"
assert_contains "T-VERIFY-REASON-ORDER-002 expected order shown" "$out1" "expected: ['RC-FS-PATH-DISALLOWED', 'RC-FS-NOT-A-FILE']"
assert_contains "T-VERIFY-REASON-ORDER-002 actual order shown" "$out1" "actual:   ['RC-FS-NOT-A-FILE', 'RC-FS-PATH-DISALLOWED']"
assert_files_equal "T-VERIFY-REASON-ORDER-002 deterministic output across runs" "$out1" "$out2"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
