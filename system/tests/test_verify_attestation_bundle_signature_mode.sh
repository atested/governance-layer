#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACK="$ROOT/scripts/attest/bundle.py"
VERIFY="$ROOT/scripts/verify-attestation-bundle.py"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/verify-attestation-sign-mode.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

FIXTURE_DIR="$ROOT/tests/fixtures/attestation_bundle/sample"
BUNDLE="$TMPDIR_LOCAL/bundle.tar"
KEY_PRIV="$TMPDIR_LOCAL/key.pem"
KEY_PUB="$TMPDIR_LOCAL/key.pub.pem"

python3 "$PACK" pack --input-dir "$FIXTURE_DIR" --out "$BUNDLE" >/dev/null

python3 - "$ROOT" "$BUNDLE" "$KEY_PRIV" "$KEY_PUB" <<'PY'
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

root = pathlib.Path(sys.argv[1])
bundle = pathlib.Path(sys.argv[2])
key_priv = pathlib.Path(sys.argv[3])
key_pub = pathlib.Path(sys.argv[4])
sys.path.insert(0, str(root / 'scripts' / 'attest'))
import ed25519_bundle_signing as s

priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex('33' * 32))
key_priv.write_bytes(
    priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
key_pub.write_bytes(
    priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)

s.write_signature_artifacts(bundle, key_priv, None, None)
PY

# PASS when signature present and valid
out_pass="$(python3 "$VERIFY" "$BUNDLE" --require-signature 1 --pubkey "$KEY_PUB")"
echo "$out_pass" | rg '^ATTESTATION_BUNDLE_VERIFY ok=yes reason=OK ' >/dev/null
echo "$out_pass" | rg ' signature_verified=yes$' >/dev/null
echo "$out_pass" | rg '^PASS: attestation bundle signature verified$' >/dev/null
echo "$out_pass" | rg '^PASS: attestation bundle manifest \+ payload hashes verified$' >/dev/null

# FAIL when signature missing and require-signature=1
rm -f "$BUNDLE.sig" "$BUNDLE.sigmeta.json"
set +e
out_missing="$(python3 "$VERIFY" "$BUNDLE" --require-signature 1 --pubkey "$KEY_PUB" 2>&1)"
rc_missing=$?
set -e
[[ $rc_missing -ne 0 ]]
echo "$out_missing" | rg '^ATTESTATION_BUNDLE_VERIFY ok=no reason=SIGNATURE_INVALID ' >/dev/null
echo "$out_missing" | rg ' signature_verified=no$' >/dev/null
echo "$out_missing" | rg '^FAIL: SIGNATURE_REQUIRED_MISSING$' >/dev/null

# FAIL on bad signature
python3 - "$ROOT" "$BUNDLE" "$KEY_PRIV" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
bundle = pathlib.Path(sys.argv[2])
key_priv = pathlib.Path(sys.argv[3])
sys.path.insert(0, str(root / 'scripts' / 'attest'))
import ed25519_bundle_signing as s

s.write_signature_artifacts(bundle, key_priv, None, None)
sp = pathlib.Path(str(bundle) + '.sig')
s = sp.read_text(encoding='utf-8').strip()
sp.write_text((s[:-1] + ('A' if s[-1] != 'A' else 'B')) + '\n', encoding='utf-8')
PY

set +e
out_bad="$(python3 "$VERIFY" "$BUNDLE" --require-signature 1 --pubkey "$KEY_PUB" 2>&1)"
rc_bad=$?
set -e
[[ $rc_bad -ne 0 ]]
echo "$out_bad" | rg '^ATTESTATION_BUNDLE_VERIFY ok=no reason=SIGNATURE_INVALID ' >/dev/null
echo "$out_bad" | rg '^FAIL: SIGNATURE_VERIFICATION_FAILED$' >/dev/null

echo "CASE=VERIFY_ATTESTATION_BUNDLE_SIGNATURE_MODE PASS"
