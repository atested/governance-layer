#!/usr/bin/env python3
"""Authenticated, scope-limited governance evidence packages.

The package is a canonical JSON artifact signed with Ed25519.  Its declared
scope, selected records, and issuer metadata are all covered by both a SHA-256
digest and the signature.  A recipient needs only the artifact and this
module's verifier; the public verification key and authentication basis are
embedded in the package.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from canonical_form import canonicalize


SCHEMA_ID = "atested.scoped-evidence.v1"
SUPPORTED_SCOPE_FIELDS = frozenset(
    {"record_ids", "subject_ids", "decisions", "machine_ids", "start_time", "end_time"}
)


class ScopedEvidenceError(ValueError):
    """A reporting scope or evidence artifact is unsafe or malformed."""


class _DuplicateKeyError(ValueError):
    pass


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * ((4 - len(value) % 4) % 4)).encode("ascii"))


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _field(record: Mapping[str, Any], name: str) -> Any:
    if name in record:
        return record.get(name)
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        return payload.get(name)
    return None


def normalize_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize a conjunctive reporting scope.

    At least one positive selector is mandatory.  This prevents an omitted or
    misspelled selector from silently becoming an all-record export.
    """
    if not isinstance(scope, Mapping):
        raise ScopedEvidenceError("reporting scope must be an object")
    unknown = sorted(set(scope) - SUPPORTED_SCOPE_FIELDS)
    if unknown:
        raise ScopedEvidenceError(f"unsupported reporting scope fields: {', '.join(unknown)}")

    normalized: dict[str, Any] = {}
    for name in ("record_ids", "subject_ids", "decisions", "machine_ids"):
        raw = scope.get(name)
        if raw is None:
            continue
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Iterable):
            raise ScopedEvidenceError(f"{name} must be a non-empty list")
        values = sorted({str(value).strip() for value in raw if str(value).strip()})
        if not values:
            raise ScopedEvidenceError(f"{name} must be a non-empty list")
        normalized[name] = values

    for name in ("start_time", "end_time"):
        if scope.get(name) is not None:
            value = str(scope[name]).strip()
            if not value:
                raise ScopedEvidenceError(f"{name} must be a non-empty timestamp")
            normalized[name] = value
    if normalized.get("start_time") and normalized.get("end_time"):
        if normalized["start_time"] > normalized["end_time"]:
            raise ScopedEvidenceError("start_time must not be after end_time")
    if not normalized:
        raise ScopedEvidenceError("reporting scope must contain at least one selector")
    return normalized


def record_matches_scope(record: Mapping[str, Any], scope: Mapping[str, Any]) -> bool:
    normalized = normalize_scope(scope)
    record_id = _field(record, "record_id") or _field(record, "request_id")
    subject_id = _field(record, "subject_id") or _field(record, "user_identity")
    decision = _field(record, "policy_decision") or _field(record, "state")
    machine_id = _field(record, "machine_id")
    timestamp = (
        _field(record, "recorded_at")
        or _field(record, "timestamp_utc")
        or _field(record, "event_timestamp_utc")
        or ""
    )
    checks = {
        "record_ids": record_id,
        "subject_ids": subject_id,
        "decisions": decision,
        "machine_ids": machine_id,
    }
    for selector, actual in checks.items():
        if selector in normalized and str(actual or "") not in normalized[selector]:
            return False
    if normalized.get("start_time") and str(timestamp) < normalized["start_time"]:
        return False
    if normalized.get("end_time") and str(timestamp) > normalized["end_time"]:
        return False
    return True


def select_scoped_records(
    records: Iterable[Mapping[str, Any]], scope: Mapping[str, Any]
) -> list[dict[str, Any]]:
    normalized = normalize_scope(scope)
    selected = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ScopedEvidenceError("every source record must be an object")
        if record_matches_scope(record, normalized):
            selected.append(deepcopy(dict(record)))
    return selected


def _public_key_info(private_key: Any) -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization

    public_key = private_key.public_key()
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    return pem, "ed25519:sha256:" + hashlib.sha256(raw).hexdigest()


def build_scoped_evidence_package(
    records: Iterable[Mapping[str, Any]],
    *,
    scope: Mapping[str, Any],
    signing_key: Any,
    issuer: str,
    created_at: str | None = None,
) -> bytes:
    """Select only in-scope records and return an authenticated JSON artifact."""
    if signing_key is None or not callable(getattr(signing_key, "sign", None)):
        raise ScopedEvidenceError("an Ed25519 signing key is required")
    identity = str(issuer or "").strip()
    if not identity:
        raise ScopedEvidenceError("issuer is required")
    normalized_scope = normalize_scope(scope)
    selected = select_scoped_records(records, normalized_scope)
    public_key_pem, key_id = _public_key_info(signing_key)
    content = {
        "schema": SCHEMA_ID,
        "package_id": "sep_" + uuid.uuid4().hex,
        "created_at": str(created_at or _now_utc_z()),
        "issuer": identity,
        "scope": normalized_scope,
        "records": selected,
    }
    content_digest = _sha256(canonicalize(content))
    signed = {
        "content": content,
        "integrity": {"algorithm": "SHA-256", "content_digest": content_digest},
        "authentication": {
            "algorithm": "Ed25519",
            "key_id": key_id,
            "public_key_pem": public_key_pem,
        },
    }
    package = dict(signed)
    package["signature"] = _b64url(signing_key.sign(canonicalize(signed)))
    return canonicalize(package) + b"\n"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def verify_scoped_evidence_package(
    package_bytes: bytes, *, expected_scope: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Independently verify structure, scope, digest, key identity, and signature."""
    errors: list[str] = []
    try:
        package = json.loads(package_bytes, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError, TypeError) as exc:
        return {"valid": False, "errors": [f"invalid package JSON: {exc}"]}
    if not isinstance(package, dict):
        return {"valid": False, "errors": ["package root must be an object"]}
    expected_package_fields = {"content", "integrity", "authentication", "signature"}
    if set(package) != expected_package_fields:
        errors.append("package fields do not match the authenticated schema")

    content = package.get("content")
    integrity = package.get("integrity")
    authentication = package.get("authentication")
    signature = package.get("signature")
    if not isinstance(content, dict):
        errors.append("content must be an object")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "SHA-256":
        errors.append("unsupported or missing integrity basis")
    if not isinstance(authentication, dict) or authentication.get("algorithm") != "Ed25519":
        errors.append("unsupported or missing authentication basis")
    if not isinstance(signature, str) or not signature:
        errors.append("signature is missing")
    if errors:
        return {"valid": False, "errors": errors}

    assert isinstance(content, dict) and isinstance(integrity, dict)
    assert isinstance(authentication, dict) and isinstance(signature, str)
    expected_content_fields = {
        "schema", "package_id", "created_at", "issuer", "scope", "records",
    }
    if set(content) != expected_content_fields:
        errors.append("content fields do not match the authenticated schema")
    if content.get("schema") != SCHEMA_ID:
        errors.append("unsupported evidence package schema")
    for field in ("package_id", "created_at", "issuer"):
        if not isinstance(content.get(field), str) or not content[field].strip():
            errors.append(f"content {field} is missing")
    records = content.get("records")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        errors.append("records must be a list of objects")
        records = []
    try:
        scope = normalize_scope(content.get("scope"))
        if expected_scope is not None and scope != normalize_scope(expected_scope):
            errors.append("declared scope does not match expected scope")
        for index, record in enumerate(records):
            if not record_matches_scope(record, scope):
                errors.append(f"record {index} is outside the declared scope")
    except ScopedEvidenceError as exc:
        scope = {}
        errors.append(str(exc))

    actual_digest = _sha256(canonicalize(content))
    digest_valid = integrity.get("content_digest") == actual_digest
    if not digest_valid:
        errors.append("content digest mismatch")

    signature_valid = False
    try:
        from cryptography.hazmat.primitives import serialization

        public_key = serialization.load_pem_public_key(
            str(authentication.get("public_key_pem") or "").encode("ascii")
        )
        raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        expected_key_id = "ed25519:sha256:" + hashlib.sha256(raw).hexdigest()
        if authentication.get("key_id") != expected_key_id:
            errors.append("authentication key identity mismatch")
        else:
            signed = {"content": content, "integrity": integrity, "authentication": authentication}
            public_key.verify(_unb64url(signature), canonicalize(signed))
            signature_valid = True
    except Exception:
        errors.append("Ed25519 signature verification failed")

    return {
        "valid": not errors,
        "schema": content.get("schema"),
        "package_id": content.get("package_id"),
        "scope": scope,
        "record_count": len(records),
        "integrity_valid": digest_valid,
        "authentication_valid": signature_valid,
        "authentication_basis": "Ed25519",
        "errors": errors,
    }
