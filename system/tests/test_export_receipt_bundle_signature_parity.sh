#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attestation_proof_contract_common.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_export_receipt_bundle_signature_parity"
OUTA="out/test_export_receipt_bundle_signature_parity_A"
OUTB="out/test_export_receipt_bundle_signature_parity_B"
SUMDIR="out/test_export_receipt_bundle_signature_parity_out"
rm -rf "$TMP_ROOT" "$OUTA" "$OUTB" "$SUMDIR" out/mcp_exec
mkdir -p "$TMP_ROOT" "$SUMDIR"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
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

src = root / "out/test_export_receipt_bundle_signature_parity/source.txt"
src.parent.mkdir(parents=True, exist_ok=True)
src.write_text("parity\n", encoding="utf-8")

req = {
    "id": "PARITY_EXEC_" + run_id,
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_export_receipt_bundle_signature_parity/source.txt",
                "dst_path": "out/test_export_receipt_bundle_signature_parity/dst_" + run_id + ".txt",
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

run_once() {
  local prefix="$1"
  local out_file="$2"
  rm -rf "$TMP_ROOT" "$OUTA" "$OUTB" out/mcp_exec
  mkdir -p "$TMP_ROOT"

  make_receipt "RID_SIG_ON" 1
  make_receipt "RID_SIG_OFF" 0

  SIG_LINE="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_SIG_ON --out-dir "$OUTA" --include-signature 1)"
  attestation_proof_require_contains "$SIG_LINE" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:SIGNED_CONTRACT"
  attestation_proof_require_kv_equal "$SIG_LINE" signature_present "yes" "FAIL:SIGNED_FLAG"

  set +e
  FAIL_OUT="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_SIG_OFF --out-dir "${OUTA}_bad" --include-signature 1 2>&1)"
  FAIL_RC=$?
  set -e
  [[ $FAIL_RC -ne 0 ]] || { echo "FAIL:EXPECTED_SIGNATURE_MISSING"; exit 1; }
  attestation_proof_require_contains "$FAIL_OUT" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=no reason=SIGNATURE_MISSING " "FAIL:SIGNATURE_MISSING_TOKEN"

  UNSIG_LINE="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_SIG_OFF --out-dir "$OUTB" --include-signature 0)"
  attestation_proof_require_contains "$UNSIG_LINE" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:UNSIGNED_CONTRACT"
  attestation_proof_require_kv_equal "$UNSIG_LINE" signature_present "no" "FAIL:UNSIGNED_FLAG"

  python3 - "$OUTA" "$OUTB" "$out_file" <<'PY'
import hashlib
import json
import pathlib
import sys

signed_dir = pathlib.Path(sys.argv[1])
unsigned_dir = pathlib.Path(sys.argv[2])
out_file = pathlib.Path(sys.argv[3])

ms = json.loads((signed_dir / "manifest.json").read_text(encoding="utf-8"))
mu = json.loads((unsigned_dir / "manifest.json").read_text(encoding="utf-8"))

if ms.get("signature_present") is not True:
    raise SystemExit("FAIL:SIGNED_MANIFEST_FALSE")
if mu.get("signature_present") is not False:
    raise SystemExit("FAIL:UNSIGNED_MANIFEST_TRUE")
if not (signed_dir / "sig/action_record.sig").is_file():
    raise SystemExit("FAIL:SIGNED_SIG_MISSING")
if not (signed_dir / "sig/action_record.sigmeta.json").is_file():
    raise SystemExit("FAIL:SIGNED_SIGMETA_MISSING")
if (unsigned_dir / "sig/action_record.sig").exists():
    raise SystemExit("FAIL:UNSIGNED_SIG_SHOULD_NOT_EXIST")

summary = {
    "signed_manifest_sha": hashlib.sha256((signed_dir / "manifest.json").read_bytes()).hexdigest(),
    "unsigned_manifest_sha": hashlib.sha256((unsigned_dir / "manifest.json").read_bytes()).hexdigest(),
    "signed_digest": ms.get("receipt_digest"),
    "unsigned_digest": mu.get("receipt_digest"),
    "signed_signature_present": ms.get("signature_present"),
    "unsigned_signature_present": mu.get("signature_present"),
}
out_file.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$SUMDIR/run1.json"
RUN2="$SUMDIR/run2.json"
run_once "A" "$RUN1"
run_once "B" "$RUN2"

_HASHES="$(attestation_proof_require_deterministic_files "$RUN1" "$RUN2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"

echo "EXPORT_RECEIPT_BUNDLE_SIGNATURE_PARITY=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
