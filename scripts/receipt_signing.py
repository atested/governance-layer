#!/usr/bin/env python3
"""Deterministic Ed25519 signing helpers for MCP receipt digests."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def _load_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except Exception as exc:  # pragma: no cover - exercised by callers in integration environments
        return None, None, None, None, f"cryptography unavailable: {exc}"
    return InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, None


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode_nopad(data: str) -> bytes:
    pad = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _public_key_fingerprint(pub: Any, serialization: Any) -> str:
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def _read_private_key(path: Path):
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"SIGNING_UNAVAILABLE:{crypto_err}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"SIGNING_KEY_UNREADABLE:{exc}")
    try:
        priv = serialization.load_pem_private_key(raw, password=None)
    except Exception as exc:
        raise ValueError(f"SIGNING_KEY_INVALID:{exc}")
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError("SIGNING_KEY_INVALID:NOT_ED25519")
    return priv, serialization


def _read_private_key_from_inline(pem_text: str):
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"SIGNING_UNAVAILABLE:{crypto_err}")
    try:
        raw = pem_text.encode("utf-8")
        priv = serialization.load_pem_private_key(raw, password=None)
    except Exception as exc:
        raise ValueError(f"SIGNING_KEY_INVALID:{exc}")
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError("SIGNING_KEY_INVALID:NOT_ED25519")
    return priv, serialization


def _read_public_key(path: Path):
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"VERIFY_UNAVAILABLE:{crypto_err}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"VERIFY_KEY_UNREADABLE:{exc}")
    try:
        pub = serialization.load_pem_public_key(raw)
    except Exception as exc:
        raise ValueError(f"VERIFY_KEY_INVALID:{exc}")
    if not isinstance(pub, Ed25519PublicKey):
        raise ValueError("VERIFY_KEY_INVALID:NOT_ED25519")
    return pub, serialization, InvalidSignature


def _read_public_key_from_inline(pem_text: str):
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"VERIFY_UNAVAILABLE:{crypto_err}")
    try:
        pub = serialization.load_pem_public_key(pem_text.encode("utf-8"))
    except Exception as exc:
        raise ValueError(f"VERIFY_KEY_INVALID:{exc}")
    if not isinstance(pub, Ed25519PublicKey):
        raise ValueError("VERIFY_KEY_INVALID:NOT_ED25519")
    return pub, serialization, InvalidSignature


def _normalize_digest(digest: str) -> str:
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError("DIGEST_FORMAT_INVALID")
    hex_part = digest.split(":", 1)[1]
    if len(hex_part) != 64 or any(ch not in "0123456789abcdef" for ch in hex_part):
        raise ValueError("DIGEST_FORMAT_INVALID")
    return digest


def sign_digest(digest: str, private_key_path: Path) -> Dict[str, str]:
    digest = _normalize_digest(digest)
    priv, serialization = _read_private_key(private_key_path)
    sig_bytes = priv.sign(digest.encode("utf-8"))
    signature = _b64url_nopad(sig_bytes)
    pub_fingerprint = _public_key_fingerprint(priv.public_key(), serialization)
    return {
        "signature": signature,
        "pubkey_fingerprint": pub_fingerprint,
    }


def sign_digest_with_key_input(digest: str, key_input: str) -> Dict[str, str]:
    digest = _normalize_digest(digest)
    if "BEGIN PRIVATE KEY" in key_input:
        priv, serialization = _read_private_key_from_inline(key_input)
    else:
        priv, serialization = _read_private_key(Path(key_input))
    sig_bytes = priv.sign(digest.encode("utf-8"))
    signature = _b64url_nopad(sig_bytes)
    pub_fingerprint = _public_key_fingerprint(priv.public_key(), serialization)
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return {
        "signature": signature,
        "pubkey_fingerprint": pub_fingerprint,
        "public_key_pem": pub_pem,
    }


def verify_digest_signature(digest: str, signature: str, public_key_path: Path) -> bool:
    digest = _normalize_digest(digest)
    pub, serialization, InvalidSignature = _read_public_key(public_key_path)
    try:
        sig_bytes = _b64url_decode_nopad(signature)
    except Exception:
        return False
    try:
        pub.verify(sig_bytes, digest.encode("utf-8"))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def write_signature_artifacts(out_dir: Path, digest: str, private_key_path: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    signed = sign_digest(digest, private_key_path)
    sig = signed["signature"]
    meta = {
        "sigmeta_version": "v0",
        "digest": digest,
        "pubkey_fingerprint": signed["pubkey_fingerprint"],
    }
    (out_dir / "action_record.sig").write_text(sig + "\n", encoding="utf-8")
    (out_dir / "action_record.sigmeta.json").write_text(
        json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {
        "signature": sig,
        "pubkey_fingerprint": signed["pubkey_fingerprint"],
    }


def verify_digest_signature_inline_pubkey(digest: str, signature: str, public_key_pem: str) -> bool:
    digest = _normalize_digest(digest)
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"VERIFY_UNAVAILABLE:{crypto_err}")
    try:
        pub = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception:
        return False
    if not isinstance(pub, Ed25519PublicKey):
        return False
    try:
        sig_bytes = _b64url_decode_nopad(signature)
        pub.verify(sig_bytes, digest.encode("utf-8"))
        return True
    except Exception:
        return False


def write_signature_artifacts_with_key_input(out_dir: Path, digest: str, key_input: str) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    signed = sign_digest_with_key_input(digest, key_input)
    sig = signed["signature"]
    meta = {
        "sigmeta_version": "v0",
        "digest": digest,
        "pubkey_fingerprint": signed["pubkey_fingerprint"],
    }
    (out_dir / "action_record.sig").write_text(sig + "\n", encoding="utf-8")
    (out_dir / "action_record.sigmeta.json").write_text(
        json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {
        "signature": sig,
        "pubkey_fingerprint": signed["pubkey_fingerprint"],
        "public_key_pem": signed["public_key_pem"],
    }


def verify_digest_signature_with_key_input(digest: str, signature: str, key_input: str) -> bool:
    digest = _normalize_digest(digest)
    if "BEGIN PUBLIC KEY" in key_input:
        try:
            pub, serialization, InvalidSignature = _read_public_key_from_inline(key_input)
        except Exception:
            return False
    else:
        try:
            pub, serialization, InvalidSignature = _read_public_key(Path(key_input))
        except Exception:
            return False
    try:
        sig_bytes = _b64url_decode_nopad(signature)
    except Exception:
        return False
    try:
        pub.verify(sig_bytes, digest.encode("utf-8"))
        return True
    except Exception:
        return False
