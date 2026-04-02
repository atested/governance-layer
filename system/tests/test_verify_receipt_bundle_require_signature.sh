#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_verify_receipt_bundle_require_signature"
SUMDIR="out/test_verify_receipt_bundle_require_signature_out"
SIGNED="out/test_verify_receipt_bundle_require_signature_signed"
UNSIGNED="out/test_verify_receipt_bundle_require_signature_unsigned"
rm -rf "$TMP_ROOT" "$SUMDIR" "$SIGNED" "$UNSIGNED" out/mcp_exec
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM="$(cat "$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem")"
PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAag0f+gOBBZ4T3SxK6bGhC2IW4MhNHvvg8cWuUcOc6k=
-----END PUBLIC KEY-----
'
WRONG_PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAj7889tGY6WF0i+V5z7mkUPkyWUsk8cGcSletQxSpcsE=
-----END PUBLIC KEY-----
'

make_receipt() {
  local run_id="$1"
  local sign_flag="$2"
  python3 - "$ROOT" "$PRIVATE_PEM" "$run_id" "$sign_flag" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]
run_id = sys.argv[3]
sign = sys.argv[4] == "1"

src = root / "out/test_verify_receipt_bundle_require_signature/source.txt"
src.parent.mkdir(parents=True, exist_ok=True)
src.write_text("require-sig\n", encoding="utf-8")

req = {
    "id": "REQSIG_EXEC_" + run_id,
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_verify_receipt_bundle_require_signature/source.txt",
                "dst_path": "out/test_verify_receipt_bundle_require_signature/dst_" + run_id + ".txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": run_id,
            "sign_receipt": sign,
            "signing_key": private_pem,
        },
    },
}
proc = subprocess.run(
    ["python3", str(root / "mcp/server.py"), "--stdio-test-capabilities-execute"],
    input=json.dumps(req, sort_keys=True, separators=(",", ":")) + "\n",
    text=True,
    capture_output=True,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit("FAIL:EXEC_RC")
res = json.loads(proc.stdout.strip())["result"]
if res.get("executed") is not True:
    raise SystemExit("FAIL:NOT_EXECUTED")
PY
}

normalize() {
  sed -E 's#out/test_verify_receipt_bundle_require_signature_(signed|unsigned)#out/test_verify_receipt_bundle_require_signature_X#g'
}

run_once() {
  local out_file="$1"
  rm -rf "$TMP_ROOT" "$SIGNED" "$UNSIGNED" out/mcp_exec
  mkdir -p "$TMP_ROOT"

  make_receipt "RID_REQ_SIG_SIGNED" 1
  make_receipt "RID_REQ_SIG_UNSIGNED" 0

  python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_REQ_SIG_SIGNED --out-dir "$SIGNED" --include-signature 1 >/dev/null
  python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_REQ_SIG_UNSIGNED --out-dir "$UNSIGNED" --include-signature 0 >/dev/null

  PASS_OUT="$(python3 scripts/verify-attestation-bundle.py "$SIGNED" --require-signature 1 --receipt-pubkey "$PUBLIC_PEM" 2>&1 | normalize)"
  echo "$PASS_OUT" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

  set +e
  MISS_OUT_RAW="$(python3 scripts/verify-attestation-bundle.py "$UNSIGNED" --require-signature 1 --receipt-pubkey "$PUBLIC_PEM" 2>&1)"
  MISS_RC=$?
  set -e
  [[ $MISS_RC -ne 0 ]] || { echo "FAIL:EXPECTED_MISSING_SIG_FAILURE"; exit 1; }
  MISS_OUT="$(echo "$MISS_OUT_RAW" | normalize)"
  echo "$MISS_OUT" | rg '^FAIL: SIGNATURE_MISSING$' >/dev/null

  set +e
  BAD_OUT_RAW="$(python3 scripts/verify-attestation-bundle.py "$SIGNED" --require-signature 1 --receipt-pubkey "$WRONG_PUBLIC_PEM" 2>&1)"
  BAD_RC=$?
  set -e
  [[ $BAD_RC -ne 0 ]] || { echo "FAIL:EXPECTED_BAD_SIG_FAILURE"; exit 1; }
  BAD_OUT="$(echo "$BAD_OUT_RAW" | normalize)"
  echo "$BAD_OUT" | rg '^FAIL: SIGNATURE_INVALID$' >/dev/null

  printf '%s\n%s\n%s\n' "$PASS_OUT" "$MISS_OUT" "$BAD_OUT" > "$out_file"
}

R1="$SUMDIR/run1.txt"
R2="$SUMDIR/run2.txt"
run_once "$R1"
run_once "$R2"

H1="$(shasum -a 256 "$R1" | awk '{print $1}')"
H2="$(shasum -a 256 "$R2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "VERIFY_RECEIPT_BUNDLE_REQUIRE_SIGNATURE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
