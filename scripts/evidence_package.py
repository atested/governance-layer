"""Encrypted evidence package builder.

Implements Phase 7 of the Chain Walker specification (section 7):
  - PBKDF2-HMAC-SHA-256 key derivation (310,000 iterations, 128-bit salt)
  - AES-256-GCM encryption (96-bit nonce)
  - ZIP package containing manifest, encrypted payload, public key,
    verification summary, and viewer placeholder

The password is never logged, stored, or written to any file.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Crypto parameters (spec section 7.1)
# ---------------------------------------------------------------------------

PBKDF2_ITERATIONS = 310_000
SALT_BYTES = 16          # 128-bit salt
NONCE_BYTES = 12         # 96-bit nonce for AES-256-GCM
KEY_BYTES = 32           # AES-256

MIN_PASSWORD_LENGTH = 12

PACKAGE_SCHEMA_VERSION = 1
PLAINTEXT_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password meets minimum length only (spec: no complexity rules)."""
    if not isinstance(password, str):
        return False, "Password must be a string."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return True, ""


# ---------------------------------------------------------------------------
# Encryption (PBKDF2 + AES-256-GCM)
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password using PBKDF2-HMAC-SHA-256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_BYTES,
    )


def encrypt_payload(plaintext: bytes, password: str) -> dict[str, Any]:
    """Encrypt plaintext with PBKDF2 + AES-256-GCM.

    Returns dict with:
      - ciphertext: bytes (nonce not prepended; stored separately in manifest)
      - salt: bytes
      - nonce: bytes
      - tag: bytes (GCM authentication tag)
      - iterations: int
    """
    # Use the cryptography library for AES-GCM
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = _derive_key(password, salt)

    aesgcm = AESGCM(key)
    # GCM appends the tag to the ciphertext; we separate them for manifest clarity
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    # cryptography library appends 16-byte tag
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]

    return {
        "ciphertext": ciphertext,
        "salt": salt,
        "nonce": nonce,
        "tag": tag,
        "iterations": PBKDF2_ITERATIONS,
    }


def decrypt_payload(
    ciphertext: bytes,
    tag: bytes,
    nonce: bytes,
    salt: bytes,
    password: str,
    iterations: int = PBKDF2_ITERATIONS,
) -> Optional[bytes]:
    """Decrypt AES-256-GCM ciphertext. Returns None on wrong password/tampered data."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=KEY_BYTES,
    )
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext + tag, None)
    except InvalidTag:
        return None


# ---------------------------------------------------------------------------
# Plaintext payload assembly
# ---------------------------------------------------------------------------

def build_plaintext_payload(
    records: list[dict],
    *,
    chain_source: str = "live",
    archive_id: str = "",
    predecessor_hash: Optional[str] = None,
    start_sequence: int = 0,
    end_sequence: int = 0,
    verification_summary: Optional[dict] = None,
    narratives: Optional[list[str]] = None,
    export_event_hash: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble the plaintext payload that will be encrypted.

    Includes predecessor context for verifying linkage at the boundary.
    """
    from chain_walker import normalize_records, narrative_for_row

    # Generate narratives from records if not provided
    if narratives is None:
        rows = normalize_records(records, start_sequence=start_sequence)
        narratives = [narrative_for_row(row) for row in rows]

    # Build verification summary if not provided
    if verification_summary is None:
        verification_summary = build_verification_summary(records)

    return {
        "schema_version": PLAINTEXT_SCHEMA_VERSION,
        "chain_source": chain_source,
        "archive_id": archive_id,
        "predecessor_hash": predecessor_hash,
        "start_sequence": start_sequence,
        "end_sequence": end_sequence,
        "records": records,
        "narratives": narratives,
        "verification_summary": verification_summary,
        "export_event_reference": export_event_hash,
    }


# ---------------------------------------------------------------------------
# Verification summary
# ---------------------------------------------------------------------------

def _load_verify_record_module():
    """Load the verify-record module for hash recomputation."""
    verify_path = Path(__file__).resolve().parent / "verify-record.py"
    spec = importlib.util.spec_from_file_location("verify_record_impl", verify_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_verifiable_record(record: dict) -> bool:
    """Check if a record has a format that verify_record_dict can handle."""
    if record.get("event_type"):
        return True  # non-action event
    if record.get("record_version") == "2.0" and record.get("record_type") == "mediated_decision":
        return True  # v2 mediated decision
    return False


def _recompute_simple_hash(record: dict) -> str:
    """Recompute a record hash using simple canonicalization.

    For records not in a recognized format (v1 legacy, test records),
    strips record_hash and computes SHA-256 of the canonical JSON.
    """
    body = {k: v for k, v in record.items() if k != "record_hash"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def build_verification_summary(records: list[dict]) -> dict[str, Any]:
    """Verify record hashes and linkage within the selected records.

    SEC-2026-003: Recomputes record hashes rather than trusting stored
    values. Uses verify_record_dict() for recognized formats (v2 mediated
    decisions, non-action events). For other records, recomputes via
    simple canonicalization. Falls back to linkage-only if verify module
    is unavailable.
    """
    if not records:
        return {"status": "empty", "record_count": 0, "verified_count": 0, "break_count": 0}

    verify_mod = _load_verify_record_module()

    verified = 0
    breaks = 0
    first_break_sequence = None
    prev_hash = None

    old_dev = os.environ.get("GOV_SIGNING_DEV_MODE")
    os.environ["GOV_SIGNING_DEV_MODE"] = "1"
    try:
        for i, record in enumerate(records):
            record_ok = True

            # Recompute and verify record hash
            if verify_mod is not None and _is_verifiable_record(record):
                rc, _lines = verify_mod.verify_record_dict(record)
                if rc != 0:
                    record_ok = False
            elif record.get("record_hash"):
                # Unrecognized format: recompute hash via simple method
                recomputed = _recompute_simple_hash(record)
                if recomputed != record["record_hash"]:
                    record_ok = False

            # Check prev_record_hash linkage
            if record_ok and i > 0 and "prev_record_hash" in record:
                linked_prev = record.get("prev_record_hash")
                if prev_hash and linked_prev and prev_hash != linked_prev:
                    record_ok = False

            if record_ok:
                verified += 1
            else:
                breaks += 1
                if first_break_sequence is None:
                    first_break_sequence = i

            prev_hash = record.get("record_hash")
    finally:
        if old_dev is None:
            os.environ.pop("GOV_SIGNING_DEV_MODE", None)
        else:
            os.environ["GOV_SIGNING_DEV_MODE"] = old_dev

    status = "verified" if breaks == 0 else "breaks_detected"
    return {
        "status": status,
        "record_count": len(records),
        "verified_count": verified,
        "break_count": breaks,
        "first_break_index": first_break_sequence,
        "first_record_hash": records[0].get("record_hash"),
        "last_record_hash": records[-1].get("record_hash"),
    }


# ---------------------------------------------------------------------------
# Package manifest
# ---------------------------------------------------------------------------

def build_manifest(
    *,
    package_id: str,
    created_at_utc: str,
    operator_identity: str,
    chain_source: str,
    archive_id: str,
    start_sequence: int,
    end_sequence: int,
    record_count: int,
    public_key_fingerprint: str,
    salt_hex: str,
    nonce_hex: str,
    iterations: int,
    ciphertext_sha256: str,
    intended_recipient: str = "",
) -> dict[str, Any]:
    """Build the package manifest.json content."""
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "created_at_utc": created_at_utc,
        "created_by": operator_identity,
        "chain_source": chain_source,
        "archive_id": archive_id,
        "range_start_sequence": start_sequence,
        "range_end_sequence": end_sequence,
        "record_count": record_count,
        "public_key_fingerprint": public_key_fingerprint,
        "encryption": {
            "algorithm": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA-256",
            "salt_hex": salt_hex,
            "nonce_hex": nonce_hex,
            "iterations": iterations,
        },
        "ciphertext_sha256": ciphertext_sha256,
        "plaintext_schema": PLAINTEXT_SCHEMA_VERSION,
        "intended_recipient": intended_recipient,
    }


# ---------------------------------------------------------------------------
# Public key helpers
# ---------------------------------------------------------------------------

def _resolve_signing_key_path_for_package(signing_key_path: Optional[str] = None) -> str:
    """Resolve signing key path for evidence packages.

    Checks explicit path, env var, hidden dotfile, and legacy visible path.
    """
    if signing_key_path:
        return signing_key_path
    explicit = os.environ.get("GOV_SIGNING_KEY_PATH", "").strip()
    if explicit:
        return explicit
    # Check hidden path in runtime directory
    runtime_dir = os.environ.get("GOV_RUNTIME_DIR", "").strip()
    if runtime_dir:
        hidden = Path(runtime_dir) / ".atested-signing-key.pem"
        if hidden.exists():
            return str(hidden)
    # Check legacy path
    repo_root = Path(__file__).resolve().parents[1]
    legacy = repo_root / "keys" / "governance-signing.pem"
    if legacy.exists():
        return str(legacy)
    return ""


def load_public_key_info(signing_key_path: Optional[str] = None) -> dict[str, Any]:
    """Load the public key from the signing key and return PEM + fingerprint."""
    key_path = _resolve_signing_key_path_for_package(signing_key_path)
    if not key_path or not Path(key_path).exists():
        return {
            "public_key_pem": "",
            "fingerprint": "no-signing-key",
        }

    try:
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
            load_pem_private_key,
        )

        pk_bytes = Path(key_path).read_bytes()
        private_key = load_pem_private_key(pk_bytes, password=None)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("ascii")
        pub_raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        fingerprint = "ed25519:sha256:" + hashlib.sha256(pub_raw).hexdigest()
        return {
            "public_key_pem": pub_pem,
            "fingerprint": fingerprint,
        }
    except Exception:
        return {
            "public_key_pem": "",
            "fingerprint": "key-load-error",
        }


# ---------------------------------------------------------------------------
# ZIP package builder
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Viewer HTML loading
# ---------------------------------------------------------------------------

_VIEWER_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "external-viewer"
_VIEWER_PATH = _VIEWER_DIR / "viewer.html"


def _load_viewer_html() -> str:
    """Load the external evidence viewer HTML.

    Returns the self-contained viewer.html content from
    dashboard/external-viewer/viewer.html. Falls back to a minimal
    placeholder if the file is not found (development/CI only).
    """
    if _VIEWER_PATH.exists():
        return _VIEWER_PATH.read_text(encoding="utf-8")
    # Fallback placeholder — should only appear if viewer.html is missing
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<title>Atested Evidence Package</title></head><body>"
        "<p>Viewer not available. Open the package files with the Atested CLI.</p>"
        "</body></html>"
    )


def build_package(
    *,
    records: list[dict],
    password: str,
    operator_identity: str,
    chain_source: str = "live",
    archive_id: str = "",
    predecessor_hash: Optional[str] = None,
    start_sequence: int = 0,
    end_sequence: int = 0,
    intended_recipient: str = "",
    export_event_hash: Optional[str] = None,
    signing_key_path: Optional[str] = None,
) -> dict[str, Any]:
    """Build a complete encrypted evidence package.

    Returns dict with:
      - zip_bytes: bytes of the ZIP file
      - package_id: unique package ID
      - manifest: the manifest dict
      - manifest_hash: SHA-256 of the manifest JSON
      - ciphertext_sha256: SHA-256 of the encrypted payload
      - record_count: number of records
    """
    # Validate password
    ok, err = validate_password(password)
    if not ok:
        raise ValueError(err)

    package_id = f"ep_{uuid.uuid4().hex[:16]}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load public key
    pk_info = load_public_key_info(signing_key_path)

    # Build verification summary
    verification = build_verification_summary(records)

    # Build plaintext payload
    payload = build_plaintext_payload(
        records,
        chain_source=chain_source,
        archive_id=archive_id,
        predecessor_hash=predecessor_hash,
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        verification_summary=verification,
        export_event_hash=export_event_hash,
    )
    plaintext_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # Encrypt
    enc = encrypt_payload(plaintext_bytes, password)
    # Combine ciphertext + tag for storage (viewer separates using known 16-byte tag length)
    encrypted_blob = enc["ciphertext"] + enc["tag"]
    ciphertext_sha256 = "sha256:" + hashlib.sha256(encrypted_blob).hexdigest()

    # Build manifest
    manifest = build_manifest(
        package_id=package_id,
        created_at_utc=created_at,
        operator_identity=operator_identity,
        chain_source=chain_source,
        archive_id=archive_id,
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        record_count=len(records),
        public_key_fingerprint=pk_info["fingerprint"],
        salt_hex=enc["salt"].hex(),
        nonce_hex=enc["nonce"].hex(),
        iterations=enc["iterations"],
        ciphertext_sha256=ciphertext_sha256,
        intended_recipient=intended_recipient,
    )

    manifest_json = json.dumps(manifest, indent=2)
    manifest_hash = "sha256:" + hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

    # Build public-key.json
    public_key_json = json.dumps({
        "public_key_pem": pk_info["public_key_pem"],
        "fingerprint": pk_info["fingerprint"],
    }, indent=2)

    # Build verification-summary.json
    verification_json = json.dumps(verification, indent=2)

    # SEC-2026-004: include viewer.html hash in manifest
    viewer_html = _load_viewer_html()
    viewer_sha256 = "sha256:" + hashlib.sha256(viewer_html.encode("utf-8")).hexdigest()
    manifest["viewer_html_sha256"] = viewer_sha256

    # Recompute manifest JSON/hash after adding viewer hash
    manifest_json = json.dumps(manifest, indent=2)
    manifest_hash = "sha256:" + hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

    # Assemble ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = "atested-evidence-package/"
        zf.writestr(f"{prefix}manifest.json", manifest_json)
        zf.writestr(f"{prefix}encrypted-chain.bin", encrypted_blob)
        zf.writestr(f"{prefix}encrypted-chain.sha256", ciphertext_sha256)
        zf.writestr(f"{prefix}public-key.json", public_key_json)
        zf.writestr(f"{prefix}verification-summary.json", verification_json)
        zf.writestr(f"{prefix}viewer.html", viewer_html)

    zip_bytes = zip_buffer.getvalue()

    return {
        "zip_bytes": zip_bytes,
        "package_id": package_id,
        "manifest": manifest,
        "manifest_hash": manifest_hash,
        "ciphertext_sha256": ciphertext_sha256,
        "record_count": len(records),
    }
