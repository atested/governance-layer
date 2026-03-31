#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_verify_receipt_attestation_bundle"
OUT_A="out/test_verify_receipt_attestation_bundle_A"
OUT_B="out/test_verify_receipt_attestation_bundle_B"
PUBKEY_FILE="$TMP_ROOT/pubkey.pem"
rm -rf "$TMP_ROOT" "$OUT_A" "$OUT_B" out/mcp_exec
mkdir -p "$TMP_ROOT"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'
PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAag0f+gOBBZ4T3SxK6bGhC2IW4MhNHvvg8cWuUcOc6k=
-----END PUBLIC KEY-----
'

make_bundle() {
  local out_dir="$1"
  printf 'verify bundle\n' > "$TMP_ROOT/src.txt"
  python3 - "$ROOT" "$PRIVATE_PEM" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]

req = {
    "id": "VERIFY_EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_verify_receipt_attestation_bundle/src.txt",
                "dst_path": "out/test_verify_receipt_attestation_bundle/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_VERIFY_BUNDLE",
            "sign_receipt": True,
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
PY
  python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_VERIFY_BUNDLE --out-dir "$out_dir" --include-signature 1 >/dev/null
}

normalize_output() {
  sed -E 's#out/test_verify_receipt_attestation_bundle_[AB]#out/test_verify_receipt_attestation_bundle_X#g'
}

printf '%s' "$PUBLIC_PEM" > "$PUBKEY_FILE"

make_bundle "$OUT_A"
PASS1="$(python3 scripts/verify-attestation-bundle.py "$OUT_A" --receipt-pubkey "$PUBKEY_FILE" 2>&1 | normalize_output)"
echo "$PASS1" | rg '^ATTESTATION_BUNDLE_VERIFY ok=yes reason=OK ' >/dev/null
echo "$PASS1" | rg ' bundle_version=attestation_bundle_v1 ' >/dev/null
echo "$PASS1" | rg ' receipt_bundle_version=receipt_attestation_bundle_v0 ' >/dev/null
echo "$PASS1" | rg ' signature_verified=not_required$' >/dev/null
echo "$PASS1" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

python3 - <<'PY'
from pathlib import Path
p = Path('out/test_verify_receipt_attestation_bundle_A/payload/record.json')
raw = p.read_text(encoding='utf-8')
p.write_text(raw.replace('"NONE"', '"NOPE"', 1), encoding='utf-8')
PY

set +e
BAD1_RAW="$(python3 scripts/verify-attestation-bundle.py "$OUT_A" --receipt-pubkey "$PUBKEY_FILE" 2>&1)"
BAD1_RC=$?
set -e
BAD1="$(echo "$BAD1_RAW" | normalize_output)"
[[ $BAD1_RC -ne 0 ]] || { echo "FAIL:NOPE_EXPECTED_FAIL"; exit 1; }
echo "$BAD1" | rg '^ATTESTATION_BUNDLE_VERIFY ok=no reason=HASH_MISMATCH ' >/dev/null
echo "$BAD1" | rg '^FAIL: hash mismatch for record\.json' >/dev/null

# Rebuild and re-run second pass for determinism.
rm -rf "$OUT_A" out/mcp_exec
make_bundle "$OUT_B"
PASS2="$(python3 scripts/verify-attestation-bundle.py "$OUT_B" --receipt-pubkey "$PUBKEY_FILE" 2>&1 | normalize_output)"
echo "$PASS2" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

python3 - <<'PY'
from pathlib import Path
p = Path('out/test_verify_receipt_attestation_bundle_B/payload/record.json')
raw = p.read_text(encoding='utf-8')
p.write_text(raw.replace('"NONE"', '"NOPE"', 1), encoding='utf-8')
PY
set +e
BAD2_RAW="$(python3 scripts/verify-attestation-bundle.py "$OUT_B" --receipt-pubkey "$PUBKEY_FILE" 2>&1)"
BAD2_RC=$?
set -e
BAD2="$(echo "$BAD2_RAW" | normalize_output)"
[[ $BAD2_RC -ne 0 ]] || { echo "FAIL:NOPE_EXPECTED_FAIL_2"; exit 1; }
echo "$BAD2" | rg '^ATTESTATION_BUNDLE_VERIFY ok=no reason=HASH_MISMATCH ' >/dev/null

N1="$TMP_ROOT/norm1.txt"
N2="$TMP_ROOT/norm2.txt"
printf '%s\n%s\n' "$PASS1" "$BAD1" > "$N1"
printf '%s\n%s\n' "$PASS2" "$BAD2" > "$N2"
H1="$(shasum -a 256 "$N1" | awk '{print $1}')"
H2="$(shasum -a 256 "$N2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "VERIFY_RECEIPT_ATTESTATION_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
