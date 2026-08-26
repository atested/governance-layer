"""Fail-closed append-only governance decision chain (SCH-GOV-001).

This is deliberately a small, dependency-light contract for producers which
need a trust-grade ledger rather than the proxy's provider-specific v2 event
shape.  It is safe to use from independent processes: the head is validated,
read, and advanced while the same lock is held.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from canonical_form import canonical_json, record_hash


SCHEMA_ID = "SCH-GOV-001"
ALLOWED_CHAIN_RECORD_TYPES = frozenset({"mediated_decision"})
_HASH_PREFIX = "sha256:"


class GovernanceChainError(RuntimeError):
    """A malformed, tampered, unsigned, or unavailable governance chain."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_hash(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith(_HASH_PREFIX)
        and len(value) == len(_HASH_PREFIX) + 64
        and all(char in "0123456789abcdef" for char in value[len(_HASH_PREFIX):])
    )


def _key_id(private_key: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return "ed25519:" + hashlib.sha256(public).hexdigest()


def _signature_preimage(record: Mapping[str, Any]) -> bytes:
    body = dict(record)
    body["signature"] = None
    body["signing_key_id"] = None
    return canonical_json(body).encode("utf-8")


def verify_signature(record: Mapping[str, Any], public_key: Any) -> None:
    """Verify a record's Ed25519 signature, including its key identifier."""
    signature = record.get("signature")
    if not isinstance(signature, str) or not isinstance(record.get("signing_key_id"), str):
        raise GovernanceChainError("record has no complete Ed25519 signature")
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature

    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    expected_id = "ed25519:" + hashlib.sha256(raw).hexdigest()
    if record["signing_key_id"] != expected_id:
        raise GovernanceChainError("signing_key_id does not match verification key")
    try:
        padded = signature + "=" * ((4 - len(signature) % 4) % 4)
        public_key.verify(base64.urlsafe_b64decode(padded.encode("ascii")), _signature_preimage(record))
    except (ValueError, InvalidSignature) as exc:
        raise GovernanceChainError("Ed25519 signature verification failed") from exc


def validate_record(record: Mapping[str, Any], *, require_signature: bool = False) -> None:
    """Validate the locked GovernanceChainRecord schema and its hash."""
    if not isinstance(record, Mapping):
        raise GovernanceChainError("chain record must be an object")
    for field in (
        "record_id", "record_type", "recorded_at", "subject_id", "payload",
        "prev_record_hash", "record_hash",
    ):
        if field not in record:
            raise GovernanceChainError(f"chain record missing required field: {field}")
    if not isinstance(record["record_id"], str) or not record["record_id"]:
        raise GovernanceChainError("record_id must be a non-empty string")
    if record["record_type"] not in ALLOWED_CHAIN_RECORD_TYPES:
        raise GovernanceChainError("record_type is not an allowed chain-record type")
    if not isinstance(record["recorded_at"], str) or not record["recorded_at"]:
        raise GovernanceChainError("recorded_at must be a non-empty timestamp")
    if not isinstance(record["subject_id"], str) or not record["subject_id"]:
        raise GovernanceChainError("subject_id must be a non-empty string")
    if not isinstance(record["payload"], Mapping):
        raise GovernanceChainError("payload must be an object")
    prev = record["prev_record_hash"]
    if prev is not None and not _valid_hash(prev):
        raise GovernanceChainError("prev_record_hash must be null or a SHA-256 digest")
    if not _valid_hash(record["record_hash"]):
        raise GovernanceChainError("record_hash must be a SHA-256 digest")
    if record_hash(dict(record)) != record["record_hash"]:
        raise GovernanceChainError("record_hash mismatch")
    signature = record.get("signature")
    key_id = record.get("signing_key_id")
    if require_signature and (not isinstance(signature, str) or not isinstance(key_id, str)):
        raise GovernanceChainError("trust-grade production record is unsigned")
    if (signature is None) != (key_id is None):
        raise GovernanceChainError("signature and signing_key_id must be present together")


class GovernanceChainRecorder:
    """Cross-process, append-only writer for ``GovernanceChainRecord`` JSONL."""

    def __init__(
        self,
        chain_path: Path,
        *,
        production: bool = False,
        signing_key: Any = None,
        lock_timeout_seconds: float = 5.0,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.production = production
        self.signing_key = signing_key
        self.lock_timeout_seconds = lock_timeout_seconds

    @contextmanager
    def _lock(self) -> Iterator[None]:
        lock_path = Path(str(self.chain_path) + ".lock.d")
        deadline = time.monotonic() + self.lock_timeout_seconds
        while True:
            try:
                lock_path.mkdir()
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise GovernanceChainError("timed out acquiring governance chain lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                lock_path.rmdir()
            except OSError:
                # Retaining a lock on an unexpected filesystem failure is
                # fail-closed: later writers time out instead of racing.
                pass

    def _read_and_validate(self) -> Optional[str]:
        if not self.chain_path.exists():
            return None
        previous: Optional[str] = None
        try:
            lines = self.chain_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise GovernanceChainError(f"unable to read chain: {exc}") from exc
        for number, line in enumerate(lines, start=1):
            if not line:
                raise GovernanceChainError(f"malformed blank chain record at line {number}")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GovernanceChainError(f"malformed chain JSON at line {number}") from exc
            validate_record(record, require_signature=self.production)
            if record["prev_record_hash"] != previous:
                raise GovernanceChainError(f"broken predecessor linkage at line {number}")
            previous = record["record_hash"]
        return previous

    def append_mediated_decision(self, *, subject_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Append one mediated-decision event, signing it in production."""
        record: dict[str, Any] = {
            "record_id": str(uuid.uuid4()),
            "record_type": "mediated_decision",
            "recorded_at": utc_now(),
            "subject_id": subject_id,
            "payload": dict(payload),
            "prev_record_hash": None,
            "record_hash": None,
            "signature": None,
            "signing_key_id": None,
        }
        with self._lock():
            head = self._read_and_validate()
            if self.production and self.signing_key is None:
                raise GovernanceChainError("production chain requires an Ed25519 signing key")
            record["prev_record_hash"] = head
            record["record_hash"] = record_hash(record)
            if self.signing_key is not None:
                record["signature"] = base64.urlsafe_b64encode(
                    self.signing_key.sign(_signature_preimage(record))
                ).decode("ascii").rstrip("=")
                record["signing_key_id"] = _key_id(self.signing_key)
            validate_record(record, require_signature=self.production)
            self.chain_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self.chain_path.open("a", encoding="utf-8") as handle:
                    handle.write(canonical_json(record) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise GovernanceChainError(f"unable to append chain record: {exc}") from exc
        return record
