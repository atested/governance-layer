"""Tests for the encrypted evidence package builder (Phase 7)."""

import json
import sys
import zipfile
import io
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from evidence_package import (
    MIN_PASSWORD_LENGTH,
    PACKAGE_SCHEMA_VERSION,
    PLAINTEXT_SCHEMA_VERSION,
    build_package,
    build_plaintext_payload,
    build_verification_summary,
    decrypt_payload,
    encrypt_payload,
    validate_password,
)


# ---------------------------------------------------------------------------
# Test records
# ---------------------------------------------------------------------------

def _record(seq, decision="ALLOW", prev_hash=None, **extra):
    import hashlib
    base = {
        "event_model_version": "0.1",
        "record_type": "mediated_decision",
        "timestamp_utc": f"2026-04-29T12:{seq:02d}:00Z",
        "request_id": f"req-{seq}",
        "user_identity": "operator@example.com",
        "original_tool": "FS_READ",
        "classification": {
            "action_type": "read",
            "targets": [f"/repo/file-{seq}.txt"],
            "confidence_tier": 1,
        },
        "policy_decision": decision,
        "prev_record_hash": prev_hash,
    }
    base.update(extra)
    canon = json.dumps(base, sort_keys=True, separators=(",", ":"))
    base["record_hash"] = "sha256:" + hashlib.sha256(canon.encode()).hexdigest()
    return base


def _chain(count=5):
    """Build a linked chain of test records."""
    records = []
    prev_hash = None
    for i in range(1, count + 1):
        r = _record(i, prev_hash=prev_hash)
        records.append(r)
        prev_hash = r["record_hash"]
    return records


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

def test_password_too_short():
    ok, err = validate_password("short")
    assert not ok
    assert str(MIN_PASSWORD_LENGTH) in err


def test_password_minimum_length():
    ok, _ = validate_password("a" * MIN_PASSWORD_LENGTH)
    assert ok


def test_password_long():
    ok, _ = validate_password("a very long passphrase that exceeds minimum requirements")
    assert ok


def test_password_not_string():
    ok, err = validate_password(12345)
    assert not ok
    assert "string" in err.lower()


# ---------------------------------------------------------------------------
# Encryption round-trip
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    plaintext = b'{"test": "data", "records": [1, 2, 3]}'
    password = "test-password-12chars"

    enc = encrypt_payload(plaintext, password)

    result = decrypt_payload(
        enc["ciphertext"],
        enc["tag"],
        enc["nonce"],
        enc["salt"],
        password,
        enc["iterations"],
    )
    assert result == plaintext


def test_wrong_password_fails():
    plaintext = b"sensitive governance data"
    password = "correct-password-123"

    enc = encrypt_payload(plaintext, password)

    result = decrypt_payload(
        enc["ciphertext"],
        enc["tag"],
        enc["nonce"],
        enc["salt"],
        "wrong-password-1234",
        enc["iterations"],
    )
    assert result is None


def test_tampered_ciphertext_fails():
    plaintext = b"chain evidence records"
    password = "good-password-here"

    enc = encrypt_payload(plaintext, password)

    tampered = bytearray(enc["ciphertext"])
    if tampered:
        tampered[0] ^= 0xFF
    result = decrypt_payload(
        bytes(tampered),
        enc["tag"],
        enc["nonce"],
        enc["salt"],
        password,
        enc["iterations"],
    )
    assert result is None


# ---------------------------------------------------------------------------
# Verification summary
# ---------------------------------------------------------------------------

def test_verification_empty():
    summary = build_verification_summary([])
    assert summary["status"] == "empty"
    assert summary["record_count"] == 0


def test_verification_linked_chain():
    records = _chain(5)
    summary = build_verification_summary(records)
    assert summary["status"] == "verified"
    assert summary["record_count"] == 5
    assert summary["break_count"] == 0
    assert summary["first_record_hash"] == records[0]["record_hash"]
    assert summary["last_record_hash"] == records[-1]["record_hash"]


def test_verification_broken_link():
    records = _chain(3)
    # Break linkage by changing prev_record_hash on record 2
    records[1]["prev_record_hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    summary = build_verification_summary(records)
    assert summary["status"] == "breaks_detected"
    assert summary["break_count"] >= 1


# ---------------------------------------------------------------------------
# Plaintext payload
# ---------------------------------------------------------------------------

def test_plaintext_payload_structure():
    records = _chain(3)
    payload = build_plaintext_payload(
        records,
        chain_source="live",
        predecessor_hash="sha256:abcd",
        start_sequence=1,
        end_sequence=3,
    )
    assert payload["schema_version"] == PLAINTEXT_SCHEMA_VERSION
    assert payload["chain_source"] == "live"
    assert payload["predecessor_hash"] == "sha256:abcd"
    assert len(payload["records"]) == 3
    assert len(payload["narratives"]) == 3
    assert payload["verification_summary"]["status"] == "verified"


# ---------------------------------------------------------------------------
# Full package build
# ---------------------------------------------------------------------------

def test_build_package_creates_valid_zip():
    records = _chain(5)
    result = build_package(
        records=records,
        password="minimum12chars!",
        operator_identity="sha256:test-operator",
        chain_source="live",
        start_sequence=1,
        end_sequence=5,
    )

    assert result["package_id"].startswith("ep_")
    assert result["record_count"] == 5
    assert result["ciphertext_sha256"].startswith("sha256:")

    # Verify ZIP structure
    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    names = zf.namelist()
    prefix = "atested-evidence-package/"
    assert f"{prefix}manifest.json" in names
    assert f"{prefix}encrypted-chain.bin" in names
    assert f"{prefix}encrypted-chain.sha256" in names
    assert f"{prefix}public-key.json" in names
    assert f"{prefix}verification-summary.json" in names
    assert f"{prefix}viewer.html" in names


def test_package_manifest_fields():
    records = _chain(3)
    result = build_package(
        records=records,
        password="secure-password-here",
        operator_identity="sha256:op-fingerprint",
        chain_source="live",
        start_sequence=10,
        end_sequence=12,
        intended_recipient="auditor@example.com",
    )

    manifest = result["manifest"]
    assert manifest["schema_version"] == PACKAGE_SCHEMA_VERSION
    assert manifest["package_id"] == result["package_id"]
    assert manifest["created_by"] == "sha256:op-fingerprint"
    assert manifest["chain_source"] == "live"
    assert manifest["range_start_sequence"] == 10
    assert manifest["range_end_sequence"] == 12
    assert manifest["record_count"] == 3
    assert manifest["intended_recipient"] == "auditor@example.com"

    enc = manifest["encryption"]
    assert enc["algorithm"] == "AES-256-GCM"
    assert enc["kdf"] == "PBKDF2-HMAC-SHA-256"
    assert enc["iterations"] == 310000
    assert len(bytes.fromhex(enc["salt_hex"])) == 16
    assert len(bytes.fromhex(enc["nonce_hex"])) == 12


def test_package_decrypt_from_zip():
    """Full round-trip: build package, extract from ZIP, decrypt."""
    records = _chain(4)
    password = "my-secure-passphrase"

    result = build_package(
        records=records,
        password=password,
        operator_identity="sha256:test",
        start_sequence=1,
        end_sequence=4,
    )

    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    prefix = "atested-evidence-package/"

    manifest = json.loads(zf.read(f"{prefix}manifest.json"))
    encrypted_blob = zf.read(f"{prefix}encrypted-chain.bin")

    enc = manifest["encryption"]
    salt = bytes.fromhex(enc["salt_hex"])
    nonce = bytes.fromhex(enc["nonce_hex"])
    iterations = enc["iterations"]

    # Separate ciphertext and tag (last 16 bytes = GCM tag)
    ciphertext = encrypted_blob[:-16]
    tag = encrypted_blob[-16:]

    plaintext = decrypt_payload(ciphertext, tag, nonce, salt, password, iterations)
    assert plaintext is not None

    payload = json.loads(plaintext)
    assert payload["schema_version"] == PLAINTEXT_SCHEMA_VERSION
    assert len(payload["records"]) == 4
    assert payload["verification_summary"]["status"] == "verified"


def test_package_wrong_password_from_zip():
    records = _chain(2)
    password = "correct-password"

    result = build_package(
        records=records,
        password=password,
        operator_identity="sha256:test",
        start_sequence=1,
        end_sequence=2,
    )

    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    prefix = "atested-evidence-package/"
    manifest = json.loads(zf.read(f"{prefix}manifest.json"))
    encrypted_blob = zf.read(f"{prefix}encrypted-chain.bin")

    enc = manifest["encryption"]
    ciphertext = encrypted_blob[:-16]
    tag = encrypted_blob[-16:]

    plaintext = decrypt_payload(
        ciphertext, tag,
        bytes.fromhex(enc["nonce_hex"]),
        bytes.fromhex(enc["salt_hex"]),
        "wrong-password-!",
        enc["iterations"],
    )
    assert plaintext is None


def test_package_short_password_rejected():
    records = _chain(1)
    try:
        build_package(
            records=records,
            password="short",
            operator_identity="sha256:test",
            start_sequence=1,
            end_sequence=1,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(MIN_PASSWORD_LENGTH) in str(e)


def test_ciphertext_sha256_matches():
    """Verify the ciphertext hash in the manifest matches the actual encrypted file."""
    import hashlib as _hl
    records = _chain(3)
    result = build_package(
        records=records,
        password="test-passphrase!",
        operator_identity="sha256:test",
        start_sequence=1,
        end_sequence=3,
    )

    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    prefix = "atested-evidence-package/"
    encrypted_blob = zf.read(f"{prefix}encrypted-chain.bin")
    sha256_stored = zf.read(f"{prefix}encrypted-chain.sha256").decode("utf-8").strip()
    computed = "sha256:" + _hl.sha256(encrypted_blob).hexdigest()

    assert sha256_stored == computed
    assert result["manifest"]["ciphertext_sha256"] == computed


def test_password_never_in_package():
    """Verify the password does not appear anywhere in the ZIP."""
    records = _chain(2)
    password = "unique-password-marker-XYZ123"

    result = build_package(
        records=records,
        password=password,
        operator_identity="sha256:test",
        start_sequence=1,
        end_sequence=2,
    )

    # Check raw ZIP bytes
    assert password.encode("utf-8") not in result["zip_bytes"]

    # Check all ZIP entries
    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    for name in zf.namelist():
        content = zf.read(name)
        assert password.encode("utf-8") not in content, f"Password found in {name}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
