#!/usr/bin/env python3
"""Shared signing and canonicalization helpers for multi-machine sync."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from receipt_signing import _b64url_decode_nopad, _b64url_nopad, _load_crypto, _public_key_fingerprint
except ImportError:  # pragma: no cover - package import path
    from scripts.receipt_signing import _b64url_decode_nopad, _b64url_nopad, _load_crypto, _public_key_fingerprint


SYNC_PROTOCOL_VERSION = "sync_v1"
DEFAULT_BASELINE_SYNC_INTERVAL_SECONDS = 300
SYNC_FAILURE_BACKOFF_SECONDS = (30, 120, 300)


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def load_public_key_pem(public_key_pem: str):
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"VERIFY_UNAVAILABLE:{crypto_err}")
    pub = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(pub, Ed25519PublicKey):
        raise ValueError("VERIFY_KEY_INVALID:NOT_ED25519")
    return pub, serialization, InvalidSignature


def public_key_fingerprint_from_pem(public_key_pem: str) -> str:
    pub, serialization, _ = load_public_key_pem(public_key_pem)
    return _public_key_fingerprint(pub, serialization)


def private_key_public_pem(private_key) -> str:
    _, serialization, _, _, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"SIGNING_UNAVAILABLE:{crypto_err}")
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def private_key_fingerprint(private_key) -> str:
    _, serialization, _, _, crypto_err = _load_crypto()
    if crypto_err:
        raise ValueError(f"SIGNING_UNAVAILABLE:{crypto_err}")
    return _public_key_fingerprint(private_key.public_key(), serialization)


def sign_preimage(preimage: str, private_key) -> str:
    return _b64url_nopad(private_key.sign(preimage.encode("utf-8")))


def verify_preimage_signature(preimage: str, signature: str, public_key_pem: str) -> bool:
    try:
        pub, _, _ = load_public_key_pem(public_key_pem)
        pub.verify(_b64url_decode_nopad(signature), preimage.encode("utf-8"))
        return True
    except Exception:
        return False


def segment_request_preimage(method: str, path: str, payload: dict, nonce: str) -> str:
    return canonical_json({
        "method": method.upper(),
        "path": path,
        "sync_session_id": payload.get("sync_session_id"),
        "request_number": payload.get("request_number"),
        "timestamp_utc": payload.get("timestamp_utc"),
        "body_hash": payload.get("segment_sha256"),
        "nonce": nonce,
        "source_machine_id": payload.get("source_machine_id"),
        "segment_id": payload.get("segment_id"),
        "segment_kind": payload.get("segment_kind"),
    })


def sign_segment_request(method: str, path: str, payload: dict, nonce: str, private_key) -> dict:
    signed = dict(payload)
    signed["remote_signature"] = sign_preimage(segment_request_preimage(method, path, signed, nonce), private_key)
    return signed


def response_preimage(path: str, payload: dict) -> str:
    body = dict(payload)
    body["primary_signature"] = None
    body["primary_signing_key_id"] = None
    return canonical_json({
        "path": path,
        "response": body,
    })


def sign_response(path: str, payload: dict, private_key, signing_key_id: Optional[str] = None) -> dict:
    signed = dict(payload)
    signed["primary_signature"] = None
    signed["primary_signing_key_id"] = None
    signed["primary_signature"] = sign_preimage(response_preimage(path, signed), private_key)
    signed["primary_signing_key_id"] = signing_key_id or private_key_fingerprint(private_key)
    return signed


def verify_response_signature(path: str, payload: dict, primary_public_key_pem: str) -> bool:
    signature = payload.get("primary_signature")
    if not isinstance(signature, str) or not signature:
        return False
    return verify_preimage_signature(response_preimage(path, payload), signature, primary_public_key_pem)


class SyncTriggerManager:
    """Small state machine for v1 sync triggers and retry backoff."""

    def __init__(self, baseline_interval_seconds: int = DEFAULT_BASELINE_SYNC_INTERVAL_SECONDS):
        self.baseline_interval_seconds = baseline_interval_seconds
        self.pending_triggers: list[str] = []
        self.last_success_epoch: Optional[float] = None
        self.failure_count = 0

    def request_sync(self, trigger: str) -> None:
        if trigger not in self.pending_triggers:
            self.pending_triggers.append(trigger)

    def next_delay_seconds(self) -> int:
        if self.failure_count <= 0:
            return self.baseline_interval_seconds
        index = min(self.failure_count - 1, len(SYNC_FAILURE_BACKOFF_SECONDS) - 1)
        return SYNC_FAILURE_BACKOFF_SECONDS[index]

    def due_triggers(self, now_epoch: float) -> list[str]:
        if self.pending_triggers:
            return list(self.pending_triggers)
        if self.last_success_epoch is None:
            return ["remote_startup"]
        if now_epoch - self.last_success_epoch >= self.baseline_interval_seconds:
            return ["periodic_baseline"]
        return []

    def mark_success(self, now_epoch: float) -> None:
        self.last_success_epoch = now_epoch
        self.failure_count = 0
        self.pending_triggers.clear()

    def mark_failure(self) -> None:
        self.failure_count += 1
