#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/attestation_proof_contract_common.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="out/test_export_receipt_attestation_bundle"
OUT_A="out/test_export_receipt_attestation_bundle_A"
OUT_B="out/test_export_receipt_attestation_bundle_B"
rm -rf "$TMP_ROOT" "$OUT_A" "$OUT_B" out/mcp_exec
mkdir -p "$TMP_ROOT"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'

make_receipt() {
  printf 'bundle\n' > "$TMP_ROOT/src.txt"
  python3 - "$ROOT" "$PRIVATE_PEM" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
private_pem = sys.argv[2]

req = {
    "id": "EXPORT_EXEC",
    "method": "capabilities.execute",
    "params": {
        "capabilities_version": "v0",
        "action": {
            "name": "FS_COPY",
            "params": {
                "src_path": "out/test_export_receipt_attestation_bundle/src.txt",
                "dst_path": "out/test_export_receipt_attestation_bundle/dst.txt",
                "overwrite": True,
            },
        },
        "mode": {
            "require_admissible": True,
            "dry_run": False,
            "run_id": "RID_EXPORT_BUNDLE",
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
payload = json.loads(proc.stdout.strip())["result"]
if payload.get("executed") is not True:
    raise SystemExit("FAIL:EXEC_NOT_EXECUTED")
PY
}

hash_bundle() {
  local dir="$1"
  python3 - "$dir" <<'PY'
import hashlib
import json
import pathlib
import sys

bundle = pathlib.Path(sys.argv[1])
manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
parts = [json.dumps(manifest, sort_keys=True, separators=(",", ":"))]
for rel in [
    "payload/record.json",
    "payload/artifacts/action_record.sha256",
    "sig/action_record.sig",
    "sig/action_record.sigmeta.json",
]:
    p = bundle / rel
    if p.is_file():
        parts.append(rel + "=" + hashlib.sha256(p.read_bytes()).hexdigest())
joined = "\n".join(parts).encode("utf-8")
print(hashlib.sha256(joined).hexdigest())
PY
}

make_receipt
EXP_A="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_EXPORT_BUNDLE --out-dir "$OUT_A" --include-signature 1)"
EXP_B="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_EXPORT_BUNDLE --out-dir "$OUT_B" --include-signature 1)"
attestation_proof_require_contains "$EXP_A" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:EXPORT_CONTRACT_A"
attestation_proof_require_contains "$EXP_B" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=yes reason=OK " "FAIL:EXPORT_CONTRACT_B"
attestation_proof_require_kv_equal "$EXP_A" signature_present "yes" "FAIL:EXPORT_SIG_FLAG_A"
attestation_proof_require_kv_equal "$EXP_A" bundle_dir "$OUT_A" "FAIL:EXPORT_DIR_A"

[[ -f "$OUT_A/manifest.json" ]] || { echo "FAIL:MANIFEST_MISSING"; exit 1; }
[[ -f "$OUT_A/payload/record.json" ]] || { echo "FAIL:RECORD_MISSING"; exit 1; }
[[ -f "$OUT_A/payload/artifacts/action_record.sha256" ]] || { echo "FAIL:DIGEST_FILE_MISSING"; exit 1; }
[[ -f "$OUT_A/sig/action_record.sig" ]] || { echo "FAIL:SIG_MISSING"; exit 1; }
[[ -f "$OUT_A/sig/action_record.sigmeta.json" ]] || { echo "FAIL:SIGMETA_MISSING"; exit 1; }

python3 - "$OUT_A/manifest.json" <<'PY'
import json
import sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
if m.get('receipt_bundle_version') != 'receipt_attestation_bundle_v0':
    raise SystemExit('FAIL:BUNDLE_VERSION')
if not str(m.get('receipt_digest', '')).startswith('sha256:'):
    raise SystemExit('FAIL:RECEIPT_DIGEST_MISSING')
if m.get('signature_present') is not True:
    raise SystemExit('FAIL:SIGNATURE_PRESENT_FALSE')
print('MANIFEST_PARSE=PASS')
PY

H1="$(hash_bundle "$OUT_A")"
H2="$(hash_bundle "$OUT_B")"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

BAD_RUN_ID="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id 'bad run id' --out-dir "$OUT_A" || true)"
attestation_proof_require_contains "$BAD_RUN_ID" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=no reason=RECEIPT_RUN_ID_INVALID " "FAIL:BAD_RUN_ID_REASON"
attestation_proof_require_kv_equal "$BAD_RUN_ID" bundle_dir "NONE" "FAIL:BAD_RUN_ID_BUNDLE_DIR"

BAD_DIGEST="$(python3 scripts/attest/export_receipt_bundle.py --receipt-digest 'sha256:not-a-digest' --out-dir "$OUT_A" || true)"
attestation_proof_require_contains "$BAD_DIGEST" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=no reason=RECEIPT_DIGEST_INVALID " "FAIL:BAD_DIGEST_REASON"
attestation_proof_require_kv_equal "$BAD_DIGEST" receipt_digest "NONE" "FAIL:BAD_DIGEST_FIELD"

BAD_OUT_DIR="$(python3 scripts/attest/export_receipt_bundle.py --receipt-run-id RID_EXPORT_BUNDLE --out-dir ../bad_export_dir || true)"
attestation_proof_require_contains "$BAD_OUT_DIR" "RECEIPT_ATTESTATION_BUNDLE_EXPORT ok=no reason=OUT_DIR_INVALID " "FAIL:BAD_OUT_DIR_REASON"
attestation_proof_require_kv_equal "$BAD_OUT_DIR" bundle_dir "NONE" "FAIL:BAD_OUT_DIR_FIELD"

echo "EXPORT_RECEIPT_ATTESTATION_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
