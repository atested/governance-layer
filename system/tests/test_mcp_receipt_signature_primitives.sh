#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_DIR="out/test_mcp_receipt_signature_primitives"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

DIGEST="sha256:1111111111111111111111111111111111111111111111111111111111111111"
BAD_DIGEST="sha256:2222222222222222222222222222222222222222222222222222222222222222"

PRIVATE_PEM="$(cat "$ROOT/system/tests/fixtures/keys/ed25519_test_private.pem")"
PUBLIC_PEM='-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAAag0f+gOBBZ4T3SxK6bGhC2IW4MhNHvvg8cWuUcOc6k=
-----END PUBLIC KEY-----
'

run_once() {
  local out_file="$1"
  rm -rf "$TMP_DIR/receipt"
  mkdir -p "$TMP_DIR/receipt"

  python3 - "$ROOT" "$DIGEST" "$BAD_DIGEST" "$out_file" "$PRIVATE_PEM" "$PUBLIC_PEM" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
digest = sys.argv[2]
bad_digest = sys.argv[3]
out_file = pathlib.Path(sys.argv[4])
priv_pem = sys.argv[5]
pub_pem = sys.argv[6]

sys.path.insert(0, str(root / "mcp"))
import receipt_signing as rs

tmp_dir = root / "out/test_mcp_receipt_signature_primitives"
priv = tmp_dir / "test_private.pem"
pub = tmp_dir / "test_public.pem"
priv.write_text(priv_pem, encoding="utf-8")
pub.write_text(pub_pem, encoding="utf-8")

art = rs.write_signature_artifacts(tmp_dir / "receipt", digest, priv)
verify_ok = rs.verify_digest_signature(digest, art["signature"], pub)
verify_bad = rs.verify_digest_signature(bad_digest, art["signature"], pub)

if not verify_ok:
    raise SystemExit("FAIL:VERIFY_OK")
if verify_bad:
    raise SystemExit("FAIL:TAMPER_NOT_DETECTED")

meta = json.loads((tmp_dir / "receipt/action_record.sigmeta.json").read_text(encoding="utf-8"))
if meta.get("digest") != digest:
    raise SystemExit("FAIL:DIGEST_BINDING")

out = {
    "signature": art["signature"],
    "pubkey_fingerprint": art["pubkey_fingerprint"],
    "verify_ok": verify_ok,
    "verify_bad": verify_bad,
}
out_file.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
}

RUN1="$TMP_DIR/run1.json"
RUN2="$TMP_DIR/run2.json"
run_once "$RUN1"
run_once "$RUN2"

H1="$(shasum -a 256 "$RUN1" | awk '{print $1}')"
H2="$(shasum -a 256 "$RUN2" | awk '{print $1}')"
[[ "$H1" == "$H2" ]] || { echo "FAIL:NON_DETERMINISTIC"; exit 1; }

echo "MCP_RECEIPT_SIGNATURE_PRIMITIVES=PASS"
echo "DETERMINISTIC=YES"
echo "RUN1_SHA256=$H1"
echo "RUN2_SHA256=$H2"
