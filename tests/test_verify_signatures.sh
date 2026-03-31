#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
VERIFY_RECORD="$ROOT/scripts/verify-record.py"
VERIFY_CHAIN="$ROOT/scripts/verify-chain.py"
FIXTURE="$ROOT/tests/fixtures/canon_001a.json"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/gov-sigverify.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

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

run_capture() {
  local outfile="$1"
  shift
  set +e
  "$@" >"$outfile" 2>&1
  local rc=$?
  set -e
  return "$rc"
}

GOV_SIGNING_DEV_MODE=1 python3 "$EVAL" "$FIXTURE" >"$tmpdir/unsigned.json"

python3 - <<'PY' "$ROOT" "$tmpdir/unsigned.json" "$tmpdir"
import base64
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

root = Path(sys.argv[1])
unsigned_path = Path(sys.argv[2])
outdir = Path(sys.argv[3])

spec = importlib.util.spec_from_file_location("verify_record_impl", root / "scripts" / "verify-record.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

rec = json.loads(unsigned_path.read_text(encoding="utf-8"))
priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

pub_pem = pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
(outdir / "verify.pub").write_bytes(pub_pem)

raw_pub = pub.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
key_id = "ed25519:" + hashlib.sha256(raw_pub).hexdigest()

preimage = mod.signing_preimage_payload(rec).encode("utf-8")
sig = priv.sign(preimage)
sig_b64u = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")

signed = copy.deepcopy(rec)
signed["signature"] = sig_b64u
signed["signing_key_id"] = key_id
(outdir / "signed.json").write_text(json.dumps(signed, indent=2, ensure_ascii=False), encoding="utf-8")

tampered = copy.deepcopy(signed)
tam_sig = bytearray(sig)
tam_sig[-1] ^= 0x01
tampered["signature"] = base64.urlsafe_b64encode(bytes(tam_sig)).decode("ascii").rstrip("=")
(outdir / "tampered-signature.json").write_text(
    json.dumps(tampered, indent=2, ensure_ascii=False), encoding="utf-8"
)

bad_key_id = copy.deepcopy(signed)
bad_key_id["signing_key_id"] = "ed25519:" + ("0" * 64)
(outdir / "bad-key-id.json").write_text(
    json.dumps(bad_key_id, indent=2, ensure_ascii=False), encoding="utf-8"
)

(outdir / "chain-good.jsonl").write_text(
    json.dumps(signed, separators=(",", ":"), ensure_ascii=False) + "\n",
    encoding="utf-8",
)
(outdir / "chain-bad-sig.jsonl").write_text(
    json.dumps(tampered, separators=(",", ":"), ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

echo "--- T-SIGVERIFY-001: verify-record accepts valid signed record ---"
out="$tmpdir/t1.out"
rc=0
run_capture "$out" env GOV_VERIFY_KEY_PATH="$tmpdir/verify.pub" python3 "$VERIFY_RECORD" "$tmpdir/signed.json" || rc=$?
check_exit "T-SIGVERIFY-001 valid signed record" "$rc" "0"
assert_contains "T-SIGVERIFY-001 output" "$out" "PASS: record_hash + signature verified"

echo
echo "--- T-SIGVERIFY-002: verify-record rejects tampered signature ---"
out="$tmpdir/t2.out"
rc=0
run_capture "$out" env GOV_VERIFY_KEY_PATH="$tmpdir/verify.pub" python3 "$VERIFY_RECORD" "$tmpdir/tampered-signature.json" || rc=$?
check_exit "T-SIGVERIFY-002 tampered signature" "$rc" "1"
assert_contains "T-SIGVERIFY-002 output" "$out" "FAIL: signature verification failed"

echo
echo "--- T-SIGVERIFY-003: verify-record rejects signing_key_id mismatch ---"
out="$tmpdir/t3.out"
rc=0
run_capture "$out" env GOV_VERIFY_KEY_PATH="$tmpdir/verify.pub" python3 "$VERIFY_RECORD" "$tmpdir/bad-key-id.json" || rc=$?
check_exit "T-SIGVERIFY-003 signing_key_id mismatch" "$rc" "1"
assert_contains "T-SIGVERIFY-003 output" "$out" "FAIL: signing_key_id mismatch"

echo
echo "--- T-SIGVERIFY-004: verify-chain enforces per-record signature verification ---"
out="$tmpdir/t4.out"
rc=0
run_capture "$out" env GOV_VERIFY_KEY_PATH="$tmpdir/verify.pub" python3 "$VERIFY_CHAIN" "$tmpdir/chain-good.jsonl" || rc=$?
check_exit "T-SIGVERIFY-004 chain valid signature" "$rc" "0"
assert_contains "T-SIGVERIFY-004 output" "$out" "PASS: chain verified (1 records)"

out="$tmpdir/t5.out"
rc=0
run_capture "$out" env GOV_VERIFY_KEY_PATH="$tmpdir/verify.pub" python3 "$VERIFY_CHAIN" "$tmpdir/chain-bad-sig.jsonl" || rc=$?
check_exit "T-SIGVERIFY-004 chain tampered signature" "$rc" "1"
assert_contains "T-SIGVERIFY-004 tampered output" "$out" "FAIL: line 1: signature verification failed"

echo
echo "Summary: pass=$pass fail=$fail"
test "$fail" -eq 0
