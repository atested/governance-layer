#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/p3-ed25519-primitive.XXXXXX")"
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

python3 - "$ROOT" "$TMPDIR_LOCAL" <<'PY'
import json
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

root = pathlib.Path(sys.argv[1])
tmp = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / "scripts" / "attest"))
import ed25519_bundle_signing as s

bundle = tmp / "bundle.tar"
bundle.write_bytes(b"deterministic-bundle-bytes\n")

a_seed = bytes.fromhex("11" * 32)
b_seed = bytes.fromhex("22" * 32)

priv_a = Ed25519PrivateKey.from_private_bytes(a_seed)
priv_b = Ed25519PrivateKey.from_private_bytes(b_seed)

pem_a = tmp / "a.pem"
pem_a.write_bytes(
    priv_a.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)

# sign then verify succeeds
digest = s.bundle_digest(bundle)
sig1, meta1 = s.sign_digest(digest, priv_a)
assert s.verify_signature(digest, sig1, meta1["signer_pubkey"]) is True

# deterministic signature for same digest+key
sig2, meta2 = s.sign_digest(digest, priv_a)
assert sig1 == sig2
assert meta1 == meta2

# tamper digest fails
try:
    s.verify_signature("sha256:" + ("0" * 64), sig1, meta1["signer_pubkey"])
    raise AssertionError("tamper digest should fail")
except Exception:
    pass

# wrong pubkey fails
wrong_pub = s.raw_public_bytes_hex(priv_b.public_key())
try:
    s.verify_signature(digest, sig1, wrong_pub)
    raise AssertionError("wrong pubkey should fail")
except Exception:
    pass

# artifact writing deterministic
sig_path_1 = tmp / "bundle.sig"
meta_path_1 = tmp / "bundle.sigmeta.json"
s.write_signature_artifacts(bundle, pem_a, sig_path_1, meta_path_1)
sig_txt_1 = sig_path_1.read_text(encoding="utf-8")
meta_txt_1 = meta_path_1.read_text(encoding="utf-8")
s.write_signature_artifacts(bundle, pem_a, sig_path_1, meta_path_1)
sig_txt_2 = sig_path_1.read_text(encoding="utf-8")
meta_txt_2 = meta_path_1.read_text(encoding="utf-8")
assert sig_txt_1 == sig_txt_2
assert meta_txt_1 == meta_txt_2

print("CASE=ED25519_PRIMITIVES PASS")
print("SIG_SHA256=" + s.sha256_bytes(sig_txt_1.encode("utf-8")))
print("META_SHA256=" + s.sha256_bytes(meta_txt_1.encode("utf-8")))
PY
