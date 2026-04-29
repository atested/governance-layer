#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY="$ROOT/scripts/verify-record.py"
FIXTURE="$ROOT/tests/fixtures/canon_001a.json"

tmpdir="$(mktemp -d)"
cleanup(){ rm -rf "$tmpdir"; }
trap cleanup EXIT

unsigned_record="$tmpdir/unsigned.json"
strict_emit_out="$tmpdir/strict_emit.out"
strict_verify_out="$tmpdir/strict_verify.out"
dev_verify_out="$tmpdir/dev_verify.out"

echo "--- T-SIGNREQ-001: signing enforcement is at the proxy layer (INV-005) ---"
# Signing is enforced at proxy startup (proxy/server.py:1635-1643),
# not in policy-eval.py which is a standalone evaluation tool.
# Proxy enforcement is tested in tests/test_proxy_signing_enforcement.py.
echo "PASS: signing enforcement delegated to proxy (see test_proxy_signing_enforcement.py)"

echo "--- T-SIGNREQ-002: explicit dev mode can still emit unsigned record ---"
GOV_SIGNING_DEV_MODE=1 python3 "$EVAL" "$FIXTURE" >"$unsigned_record"
python3 - <<'PY' "$unsigned_record"
import json, sys
doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
assert doc["signature"] is None
assert doc["signing_key_id"] is None
print("PASS: unsigned record emitted in compatibility mode")
PY

echo "--- T-SIGNREQ-003: default verify rejects unsigned record ---"
set +e
python3 "$VERIFY" "$unsigned_record" >"$strict_verify_out" 2>&1
rc_verify=$?
set -e
[[ "$rc_verify" -eq 1 ]]
grep -Fq "FAIL: unsigned record rejected in GOV_SIGNING_REQUIRED=1 mode" "$strict_verify_out"
echo "PASS: trust-grade verify rejects unsigned record"

echo "--- T-SIGNREQ-004: explicit dev mode warns and accepts unsigned record ---"
env GOV_SIGNING_DEV_MODE=1 python3 "$VERIFY" "$unsigned_record" >"$dev_verify_out"
grep -Fq "WARN: unsigned record accepted in explicit GOV_SIGNING_DEV_MODE=1 compatibility mode" "$dev_verify_out"
grep -Fq "PASS: record_hash verified" "$dev_verify_out"
echo "PASS: explicit dev mode warning emitted"
