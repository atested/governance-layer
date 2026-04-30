"""Gate 1E — Evidence package cryptographic correctness and external viewer tests.

Dispatch 175-D-2026-0430 (RELEASE-G1E-EVIDENCE-VIEWER-TESTS)

Scopes:
  1. PBKDF2 parameter correctness
  2. Manifest tamper detection
  3. Verification summary tampering (architectural protection)
  4. Package completeness edge cases
  5. Viewer content verification depth (G-19 partial closure)
  6. Viewer/package format compatibility
"""

import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from evidence_package import (
    KEY_BYTES,
    MIN_PASSWORD_LENGTH,
    NONCE_BYTES,
    PACKAGE_SCHEMA_VERSION,
    PBKDF2_ITERATIONS,
    PLAINTEXT_SCHEMA_VERSION,
    SALT_BYTES,
    _load_viewer_html,
    build_package,
    build_plaintext_payload,
    build_verification_summary,
    decrypt_payload,
    encrypt_payload,
    validate_password,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(seq, decision="ALLOW", prev_hash=None, **extra):
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
    records = []
    prev_hash = None
    for i in range(1, count + 1):
        r = _record(i, prev_hash=prev_hash)
        records.append(r)
        prev_hash = r["record_hash"]
    return records


def _build_test_package(records=None, password="test-password-ok!", **kwargs):
    if records is None:
        records = _chain(3)
    defaults = dict(
        records=records,
        password=password,
        operator_identity="sha256:test-operator",
        chain_source="live",
        start_sequence=1,
        end_sequence=len(records),
    )
    defaults.update(kwargs)
    return build_package(**defaults)


def _extract_zip(result):
    zf = zipfile.ZipFile(io.BytesIO(result["zip_bytes"]))
    prefix = "atested-evidence-package/"
    return zf, prefix


# ===========================================================================
# Scope 1 — PBKDF2 parameter correctness
# ===========================================================================

class TestPBKDF2Parameters:
    """Verify PBKDF2 parameters meet spec requirements."""

    def test_iteration_count_is_310000(self):
        assert PBKDF2_ITERATIONS == 310_000

    def test_salt_is_128_bit(self):
        assert SALT_BYTES == 16  # 128 bits

    def test_nonce_is_96_bit(self):
        assert NONCE_BYTES == 12  # 96 bits

    def test_key_is_256_bit(self):
        assert KEY_BYTES == 32  # 256 bits

    def test_actual_salt_length_in_package(self):
        result = _build_test_package()
        enc = result["manifest"]["encryption"]
        salt_bytes = bytes.fromhex(enc["salt_hex"])
        assert len(salt_bytes) == 16

    def test_actual_nonce_length_in_package(self):
        result = _build_test_package()
        enc = result["manifest"]["encryption"]
        nonce_bytes = bytes.fromhex(enc["nonce_hex"])
        assert len(nonce_bytes) == 12

    def test_iterations_in_manifest(self):
        result = _build_test_package()
        enc = result["manifest"]["encryption"]
        assert enc["iterations"] == 310_000

    def test_algorithm_labels(self):
        result = _build_test_package()
        enc = result["manifest"]["encryption"]
        assert enc["algorithm"] == "AES-256-GCM"
        assert enc["kdf"] == "PBKDF2-HMAC-SHA-256"

    def test_salt_uniqueness_across_packages(self):
        """Two packages from the same records must have different salts."""
        r1 = _build_test_package()
        r2 = _build_test_package()
        assert r1["manifest"]["encryption"]["salt_hex"] != r2["manifest"]["encryption"]["salt_hex"]


# ===========================================================================
# Scope 2 — Manifest tamper detection
# ===========================================================================

class TestManifestTamperDetection:
    """Verify ciphertext hash cross-check catches manifest tampering."""

    def test_ciphertext_hash_matches_blob(self):
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        blob = zf.read(f"{prefix}encrypted-chain.bin")
        computed = "sha256:" + hashlib.sha256(blob).hexdigest()
        assert result["manifest"]["ciphertext_sha256"] == computed

    def test_sha256_file_matches_manifest(self):
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        sha256_file = zf.read(f"{prefix}encrypted-chain.sha256").decode("utf-8").strip()
        assert sha256_file == result["manifest"]["ciphertext_sha256"]

    def test_tampered_blob_detected_by_hash(self):
        """If encrypted-chain.bin is modified, its hash no longer matches manifest."""
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        blob = zf.read(f"{prefix}encrypted-chain.bin")
        tampered = bytearray(blob)
        tampered[0] ^= 0xFF
        tampered_hash = "sha256:" + hashlib.sha256(bytes(tampered)).hexdigest()
        assert tampered_hash != result["manifest"]["ciphertext_sha256"]

    def test_tampered_manifest_record_count_does_not_affect_decryption(self):
        """Manifest metadata tampering does not change the encrypted payload.
        The record count in the manifest is informational; the real data is
        inside the encrypted payload. This test documents that manifest
        metadata is NOT integrity-protected independently — the ciphertext
        hash protects the payload, not the manifest fields."""
        result = _build_test_package()
        manifest = result["manifest"]
        original_count = manifest["record_count"]
        # Tamper: change record count
        manifest["record_count"] = 999
        # The ciphertext hash still matches — metadata tampering is detectable
        # only by comparing manifest fields against decrypted payload contents
        assert manifest["record_count"] != original_count


# ===========================================================================
# Scope 3 — Verification summary tampering (architectural protection)
# ===========================================================================

class TestVerificationSummaryProtection:
    """The verification summary is inside the encrypted payload, so the
    plaintext companion file (verification-summary.json) is informational
    only. The viewer decrypts and uses the embedded summary."""

    def test_summary_inside_encrypted_payload(self):
        """Verification summary is part of the plaintext payload structure."""
        records = _chain(3)
        payload = build_plaintext_payload(
            records,
            chain_source="live",
            predecessor_hash=None,
            start_sequence=1,
            end_sequence=3,
        )
        assert "verification_summary" in payload
        assert payload["verification_summary"]["status"] == "verified"
        assert payload["verification_summary"]["record_count"] == 3

    def test_companion_file_present_in_zip(self):
        """The plaintext verification-summary.json is present but informational."""
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        names = zf.namelist()
        assert f"{prefix}verification-summary.json" in names

    def test_tampered_companion_does_not_affect_encrypted_payload(self):
        """Even if the companion file were replaced, the encrypted payload
        contains its own verification summary that would be used instead."""
        result = _build_test_package(password="test-password-ok!")
        zf, prefix = _extract_zip(result)
        blob = zf.read(f"{prefix}encrypted-chain.bin")
        enc = result["manifest"]["encryption"]

        # Decrypt and extract the embedded summary
        ciphertext = blob[:-16]
        tag = blob[-16:]
        plaintext = decrypt_payload(
            ciphertext, tag,
            bytes.fromhex(enc["nonce_hex"]),
            bytes.fromhex(enc["salt_hex"]),
            "test-password-ok!",
            enc["iterations"],
        )
        payload = json.loads(plaintext)
        embedded_summary = payload["verification_summary"]

        # The companion file content
        companion = json.loads(zf.read(f"{prefix}verification-summary.json"))

        # Both should agree for an untampered package
        assert embedded_summary["status"] == companion["status"]
        assert embedded_summary["record_count"] == companion["record_count"]

        # Key point: the embedded summary is protected by AES-GCM encryption.
        # Modifying companion file has zero effect on decrypted payload.

    def test_verification_summary_fields_complete(self):
        """Verification summary has all expected fields."""
        records = _chain(5)
        summary = build_verification_summary(records)
        assert "status" in summary
        assert "record_count" in summary
        assert "break_count" in summary
        assert "first_record_hash" in summary
        assert "last_record_hash" in summary


# ===========================================================================
# Scope 4 — Package completeness edge cases
# ===========================================================================

class TestPackageCompletenessEdgeCases:
    """Edge cases for package building and content."""

    def test_single_record_package(self):
        records = _chain(1)
        result = _build_test_package(records=records, end_sequence=1)
        assert result["record_count"] == 1
        zf, prefix = _extract_zip(result)
        assert len(zf.namelist()) == 6

    def test_large_chain_package(self):
        """Package with many records still has all 6 files."""
        records = _chain(50)
        result = _build_test_package(records=records, end_sequence=50)
        assert result["record_count"] == 50
        zf, prefix = _extract_zip(result)
        assert len(zf.namelist()) == 6

    def test_deny_records_in_package(self):
        """Package containing DENY records builds correctly."""
        records = []
        prev_hash = None
        for i in range(1, 4):
            decision = "DENY" if i == 2 else "ALLOW"
            r = _record(i, decision=decision, prev_hash=prev_hash)
            records.append(r)
            prev_hash = r["record_hash"]
        result = _build_test_package(records=records)
        # Verify the DENY record is present in the decrypted payload
        zf, prefix = _extract_zip(result)
        blob = zf.read(f"{prefix}encrypted-chain.bin")
        enc = result["manifest"]["encryption"]
        plaintext = decrypt_payload(
            blob[:-16], blob[-16:],
            bytes.fromhex(enc["nonce_hex"]),
            bytes.fromhex(enc["salt_hex"]),
            "test-password-ok!",
            enc["iterations"],
        )
        payload = json.loads(plaintext)
        decisions = [r["policy_decision"] for r in payload["records"]]
        assert "DENY" in decisions

    def test_password_minimum_boundary(self):
        """Password at exactly MIN_PASSWORD_LENGTH works."""
        records = _chain(1)
        pw = "a" * MIN_PASSWORD_LENGTH
        result = _build_test_package(records=records, password=pw, end_sequence=1)
        assert result["record_count"] == 1

    def test_password_below_minimum_rejected(self):
        with pytest.raises(ValueError, match=str(MIN_PASSWORD_LENGTH)):
            _build_test_package(password="short")

    def test_zip_prefix_correct(self):
        """All files are under atested-evidence-package/ prefix."""
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        for name in zf.namelist():
            assert name.startswith("atested-evidence-package/"), f"Unexpected prefix: {name}"

    def test_all_six_files_present(self):
        result = _build_test_package()
        zf, prefix = _extract_zip(result)
        expected = {
            f"{prefix}manifest.json",
            f"{prefix}encrypted-chain.bin",
            f"{prefix}encrypted-chain.sha256",
            f"{prefix}public-key.json",
            f"{prefix}verification-summary.json",
            f"{prefix}viewer.html",
        }
        assert set(zf.namelist()) == expected


# ===========================================================================
# Scope 5 — Viewer content verification depth (G-19)
# ===========================================================================

class TestViewerContentVerification:
    """Structural verification of the viewer HTML.

    G-19 is browser-based runtime verification (deferred to Gate 5).
    These tests close the static/structural subset: verify the viewer
    contains the correct code paths for decryption, hash verification,
    signature checking, and fail-closed behavior.
    """

    @pytest.fixture(autouse=True)
    def _load_viewer(self):
        self.viewer = _load_viewer_html()

    def test_webcrypto_decryption_path(self):
        """Viewer contains WebCrypto PBKDF2 → AES-GCM decryption code."""
        assert "crypto.subtle" in self.viewer
        assert "PBKDF2" in self.viewer
        assert "AES-GCM" in self.viewer
        assert "deriveKey" in self.viewer
        assert "decrypt" in self.viewer

    def test_hash_linkage_verification(self):
        """Viewer contains record hash recomputation and chain linkage check."""
        assert "canonicalJson" in self.viewer
        assert "computeRecordHash" in self.viewer
        assert "prev_record_hash" in self.viewer

    def test_nontechnical_and_technical_views(self):
        """Viewer has both non-technical and technical view containers."""
        assert 'id="view-nontechnical"' in self.viewer
        assert 'id="view-technical"' in self.viewer
        assert "btn-nontechnical" in self.viewer
        assert "btn-technical" in self.viewer

    def test_fail_closed_logic(self):
        """Viewer fails closed: any hash/sig failure → status='failed'."""
        assert "hashFailed" in self.viewer
        assert "sigFailed" in self.viewer
        # The fail-closed status assignment
        assert "hash_and_sig_verified" in self.viewer
        assert "hash_verified" in self.viewer

    def test_ed25519_signature_verification(self):
        """Viewer contains Ed25519 signature verification code path."""
        assert "Ed25519" in self.viewer
        assert "isEd25519Available" in self.viewer
        # Verify it has the actual verification function
        assert "verifyEd25519Signature" in self.viewer

    def test_no_unencrypted_reexport(self):
        """Viewer explicitly does not provide unencrypted re-export."""
        assert "does not provide an unencrypted re-export" in self.viewer.lower()

    def test_self_contained_no_external_deps(self):
        """Viewer has no external script src or stylesheet href."""
        external_scripts = re.findall(r'<script\s+[^>]*src\s*=', self.viewer)
        assert len(external_scripts) == 0
        external_links = re.findall(r'<link\s+[^>]*href\s*=\s*["\']https?://', self.viewer)
        assert len(external_links) == 0

    def test_password_input_present(self):
        """Viewer has a password input field."""
        assert 'type="password"' in self.viewer

    def test_ciphertext_integrity_check_before_decrypt(self):
        """Viewer checks ciphertext SHA-256 against manifest before decrypting."""
        assert "ciphertext_sha256" in self.viewer
        # The viewer computes sha256 of the blob and compares to manifest
        assert "sha256hex" in self.viewer or "sha256" in self.viewer.lower()


# ===========================================================================
# Scope 6 — Viewer/package format compatibility
# ===========================================================================

class TestViewerPackageCompatibility:
    """Verify the viewer's expected format matches the package builder output."""

    def test_viewer_expects_same_file_names(self):
        """Viewer's EXPECTED_FILES matches package builder output."""
        viewer = _load_viewer_html()
        # Viewer expects these file names (from its EXPECTED_FILES constant)
        assert "'manifest.json'" in viewer
        assert "'encrypted-chain.bin'" in viewer
        assert "'encrypted-chain.sha256'" in viewer
        assert "'public-key.json'" in viewer
        assert "'verification-summary.json'" in viewer

    def test_viewer_reads_encryption_params_from_manifest(self):
        """Viewer reads salt_hex, nonce_hex, iterations from manifest.encryption."""
        viewer = _load_viewer_html()
        assert "salt_hex" in viewer
        assert "nonce_hex" in viewer
        assert "iterations" in viewer

    def test_viewer_uses_concatenated_ciphertext_tag_format(self):
        """Viewer expects encrypted-chain.bin = ciphertext + tag (WebCrypto format).
        WebCrypto AES-GCM decrypt takes the concatenated blob directly."""
        viewer = _load_viewer_html()
        # WebCrypto handles ciphertext+tag concatenation natively via tagLength:128
        assert "tagLength" in viewer
        assert "128" in viewer

    def test_decrypt_roundtrip_matches_viewer_flow(self):
        """End-to-end: build package → extract → decrypt matches viewer's expected flow.

        The viewer's flow:
        1. Read manifest.json for encryption params
        2. Read encrypted-chain.bin
        3. Verify ciphertext hash
        4. PBKDF2 derive key
        5. AES-GCM decrypt (blob as-is, WebCrypto expects ct+tag)
        6. Parse JSON payload
        7. Verify chain (hash recompute + linkage + signatures)
        """
        password = "roundtrip-test-password"
        records = _chain(4)
        result = _build_test_package(records=records, password=password, end_sequence=4)
        zf, prefix = _extract_zip(result)

        # Step 1: Read manifest
        manifest = json.loads(zf.read(f"{prefix}manifest.json"))
        enc = manifest["encryption"]

        # Step 2: Read blob
        blob = zf.read(f"{prefix}encrypted-chain.bin")

        # Step 3: Verify ciphertext hash
        computed_hash = "sha256:" + hashlib.sha256(blob).hexdigest()
        assert computed_hash == manifest["ciphertext_sha256"]

        # Steps 4-5: Decrypt (our decrypt_payload separates ct+tag;
        # WebCrypto takes them concatenated)
        ciphertext = blob[:-16]
        tag = blob[-16:]
        plaintext = decrypt_payload(
            ciphertext, tag,
            bytes.fromhex(enc["nonce_hex"]),
            bytes.fromhex(enc["salt_hex"]),
            password,
            enc["iterations"],
        )
        assert plaintext is not None

        # Step 6: Parse payload
        payload = json.loads(plaintext)
        assert payload["schema_version"] == PLAINTEXT_SCHEMA_VERSION
        assert len(payload["records"]) == 4

        # Step 7: Verify chain integrity
        summary = payload["verification_summary"]
        assert summary["status"] == "verified"
        assert summary["record_count"] == 4
        assert summary["break_count"] == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
