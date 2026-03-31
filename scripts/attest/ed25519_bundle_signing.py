#!/usr/bin/env python3
"""Deterministic Ed25519 signing primitives for attestation bundles."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def bundle_digest(bundle_path: Path) -> str:
    return sha256_bytes(bundle_path.read_bytes())


def load_private_key_pem(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    return key


def load_public_key_pem(path: Path) -> Ed25519PublicKey:
    raw = path.read_bytes()
    key = serialization.load_pem_public_key(raw)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("public key is not Ed25519")
    return key


def raw_public_bytes_hex(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return raw.hex()


def canonical_signature_message(bundle_digest_value: str, signer_pubkey_hex: str) -> bytes:
    payload = {
        "bundle_digest": bundle_digest_value,
        "signer_pubkey": signer_pubkey_hex,
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sign_digest(bundle_digest_value: str, private_key: Ed25519PrivateKey) -> Tuple[str, Dict[str, str]]:
    pub = private_key.public_key()
    signer_pubkey = raw_public_bytes_hex(pub)
    msg = canonical_signature_message(bundle_digest_value, signer_pubkey)
    sig = private_key.sign(msg)
    sig_b64u = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    meta = {
        "bundle_digest": bundle_digest_value,
        "signer_pubkey": signer_pubkey,
        "signature_scheme": "ed25519_attestation_bundle_v0",
    }
    return sig_b64u, meta


def verify_signature(bundle_digest_value: str, signature_b64u: str, signer_pubkey_hex: str) -> bool:
    msg = canonical_signature_message(bundle_digest_value, signer_pubkey_hex)
    sig = base64.urlsafe_b64decode(signature_b64u + "=" * ((4 - len(signature_b64u) % 4) % 4))
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer_pubkey_hex))
    pub.verify(sig, msg)
    return True


def default_signature_paths(bundle_path: Path) -> Tuple[Path, Path]:
    sig_path = Path(str(bundle_path) + ".sig")
    meta_path = Path(str(bundle_path) + ".sigmeta.json")
    return sig_path, meta_path


def write_signature_artifacts(bundle_path: Path, private_key_path: Path, sig_out: Path | None, meta_out: Path | None) -> Tuple[Path, Path]:
    digest = bundle_digest(bundle_path)
    priv = load_private_key_pem(private_key_path)
    signature, meta = sign_digest(digest, priv)

    if sig_out is None or meta_out is None:
        default_sig, default_meta = default_signature_paths(bundle_path)
        sig_out = default_sig if sig_out is None else sig_out
        meta_out = default_meta if meta_out is None else meta_out

    sig_out.parent.mkdir(parents=True, exist_ok=True)
    meta_out.parent.mkdir(parents=True, exist_ok=True)
    sig_out.write_text(signature + "\n", encoding="utf-8")
    meta_out.write_text(json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return sig_out, meta_out


def main() -> int:
    ap = argparse.ArgumentParser(description="Create detached Ed25519 signature artifacts for an attestation bundle")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--private-key", required=True)
    ap.add_argument("--sig-out")
    ap.add_argument("--sigmeta-out")
    args = ap.parse_args()

    bundle_path = Path(args.bundle)
    private_key_path = Path(args.private_key)
    sig_out = Path(args.sig_out) if args.sig_out else None
    sigmeta_out = Path(args.sigmeta_out) if args.sigmeta_out else None

    sig_path, sigmeta_path = write_signature_artifacts(bundle_path, private_key_path, sig_out, sigmeta_out)
    _ = (sig_path, sigmeta_path)
    print("SIGNATURE_SCHEME=ed25519_attestation_bundle_v0")
    print(f"BUNDLE_DIGEST={bundle_digest(bundle_path)}")
    print("SIGNATURE_ARTIFACTS_WRITTEN=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
