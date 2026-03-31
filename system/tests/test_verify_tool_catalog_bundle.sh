#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/helpers/tool_catalog_contract_common.sh"
ROOT="$(tool_catalog_repo_root "${BASH_SOURCE[0]}")"
cd "$ROOT"

TMP_ROOT="out/test_verify_tool_catalog_bundle"
OUT1="out/test_verify_tool_catalog_bundle_A"
OUT2="out/test_verify_tool_catalog_bundle_B"
tool_catalog_reset_dir "$TMP_ROOT"
tool_catalog_reset_catalog_runtime
rm -rf "$OUT1" "$OUT2"

PRIVATE_PEM='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPFVBLmFaiKlEPwC2vjcA6z2OTsG0euiU2Gq4CzhG+7D
-----END PRIVATE KEY-----
'
PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAag0f+gOBBZ4T3SxK6bGhC2IW4MhNHvvg8cWuUcOc6k=
-----END PUBLIC KEY-----
'

python3 - "$ROOT" <<'PY'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "mcp"))
from tool_catalog_store import put  # noqa: E402
put(root, {
    "tool_name": "verify_alpha",
    "tool_version": "1.0.0",
    "schema_json": {"v": 1, "kind": "verify"},
    "declared_capabilities": ["FS_COPY", "FS_MOVE"],
    "created_from": "external",
})
PY

python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT1" --sign 1 --private-key "$PRIVATE_PEM" >/dev/null
OK="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT1" --require-signature 1 --pubkey "$PUBLIC_PEM")"
tool_catalog_require_status_line "$OK" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:VERIFY_OK" ok=yes reason=OK signature_verified=yes
tool_catalog_require_kv_present "$OK" bundle_id "FAIL:VERIFY_OK_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$OK" manifest_sha256 "FAIL:VERIFY_OK_MANIFEST_SHA_MISSING"

python3 - "$OUT1" <<'PY'
import pathlib
import json
import sys
bundle = pathlib.Path(sys.argv[1])
manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
target = bundle / manifest["files"][0]["path"]
raw = bytearray(target.read_bytes())
raw[0] = (raw[0] + 1) % 256
target.write_bytes(bytes(raw))
PY

set +e
BAD="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT1" --require-signature 0)"
RC=$?
set -e
[[ $RC -ne 0 ]] || { echo "FAIL:TAMPER_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$BAD" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:BAD_REASON" ok=no reason=HASH_MISMATCH signature_verified=not_required
tool_catalog_require_kv_present "$BAD" bundle_id "FAIL:BAD_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$BAD" manifest_sha256 "FAIL:BAD_MANIFEST_SHA_MISSING"

python3 scripts/attest/export_tool_catalog_bundle.py --out-dir "$OUT2" --sign 1 --private-key "$PRIVATE_PEM" >/dev/null
OK2="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT2" --require-signature 1 --pubkey "$PUBLIC_PEM")"
tool_catalog_require_status_line "$OK2" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:VERIFY_OK_2" ok=yes reason=OK signature_verified=yes
tool_catalog_require_kv_present "$OK2" bundle_id "FAIL:VERIFY_OK_2_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$OK2" manifest_sha256 "FAIL:VERIFY_OK_2_MANIFEST_SHA_MISSING"

python3 - "$OUT2/manifest.json" <<'PY'
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
p.write_text("{bad-json}\n", encoding="utf-8")
PY
set +e
MALFORMED="$(python3 scripts/attest/verify_tool_catalog_bundle.py --bundle-dir "$OUT2" --require-signature 0)"
RC=$?
set -e
[[ $RC -ne 0 ]] || { echo "FAIL:MALFORMED_MANIFEST_SHOULD_FAIL"; exit 1; }
tool_catalog_require_status_line "$MALFORMED" "TOOL_CATALOG_BUNDLE_VERIFY " "FAIL:MALFORMED_REASON" ok=no reason=MANIFEST_INVALID signature_verified=not_required
tool_catalog_require_kv_present "$MALFORMED" bundle_id "FAIL:MALFORMED_BUNDLE_ID_MISSING"
tool_catalog_require_kv_present "$MALFORMED" manifest_sha256 "FAIL:MALFORMED_MANIFEST_SHA_MISSING"

SUM1="$TMP_ROOT/sum1.txt"
SUM2="$TMP_ROOT/sum2.txt"
printf '%s\n%s\n' "$OK" "$BAD" > "$SUM1"
printf '%s\n%s\n' "$OK2" "$BAD" > "$SUM2"
_HASHES="$(tool_catalog_require_deterministic_files "$SUM1" "$SUM2" "FAIL:NON_DETERMINISTIC")"
H1="$(printf '%s\n' "$_HASHES" | sed -n '1p')"
H2="$(printf '%s\n' "$_HASHES" | sed -n '2p')"
tool_catalog_require_equal "$H1" "$H2" "FAIL:NON_DETERMINISTIC"

echo "VERIFY_TOOL_CATALOG_BUNDLE=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
