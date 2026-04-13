#!/usr/bin/env python3
"""
test_v2_signing.py — Tests for Ed25519 signing of v2 mediated_decision records.

Covers:
- Unsigned v2 records verify (backward compatibility)
- Signed v2 records verify (hash + signature)
- Mixed chain: unsigned followed by signed records
- Tampered signature fails verification
- Missing key_id with present signature fails
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
MCP = REPO / "mcp"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(MCP) not in sys.path:
    sys.path.insert(0, str(MCP))

from receipt_signing import _b64url_nopad, _public_key_fingerprint

# Import verify-record.py (hyphenated filename)
import importlib.util
_spec = importlib.util.spec_from_file_location("verify_record_mod", SCRIPTS / "verify-record.py")
_vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vr)
verify_record_dict = _vr.verify_record_dict
signing_preimage_payload = _vr.signing_preimage_payload
_verify_v2_mediated_decision = _vr._verify_v2_mediated_decision


def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_v2_hash(record):
    """Compute v2 record_hash: sha256 of canonical JSON with record_hash=None."""
    hashable = dict(record)
    hashable["record_hash"] = None
    if "signature" in hashable:
        hashable["signature"] = None
    if "signing_key_id" in hashable:
        hashable["signing_key_id"] = None
    canonical = _canonical_json(hashable)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_unsigned_v2_record(**overrides):
    """Create a minimal valid unsigned v2 mediated_decision record."""
    record = {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-04-13T00:00:00Z",
        "session_id": "test-session",
        "request_id": "req-001",
        "process_id": 12345,
        "original_tool": "Read",
        "classification": {
            "action_type": "read",
            "confidence_tier": 1,
            "scope": "local",
            "targets": ["/tmp/test.txt"],
        },
        "policy_decision": "ALLOW",
        "matched_rule": "read-source-allow",
        "policy_reasons": [],
        "prev_record_hash": None,
    }
    record.update(overrides)
    record["record_hash"] = _compute_v2_hash(record)
    return record


def _make_signed_v2_record(priv_key, serialization, **overrides):
    """Create a minimal valid signed v2 mediated_decision record."""
    record = {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": "2026-04-13T00:01:00Z",
        "session_id": "test-session",
        "request_id": "req-002",
        "process_id": 12345,
        "original_tool": "Write",
        "classification": {
            "action_type": "write",
            "confidence_tier": 1,
            "scope": "local",
            "targets": ["/tmp/test.txt"],
        },
        "policy_decision": "ALLOW",
        "matched_rule": "write-source-allow",
        "policy_reasons": [],
        "prev_record_hash": None,
        "signature": None,
        "signing_key_id": None,
    }
    record.update(overrides)
    # Compute hash with signature fields null
    record["record_hash"] = _compute_v2_hash(record)
    # Sign
    preimage = signing_preimage_payload(record)
    sig_bytes = priv_key.sign(preimage.encode("utf-8"))
    record["signature"] = _b64url_nopad(sig_bytes)
    record["signing_key_id"] = _public_key_fingerprint(
        priv_key.public_key(), serialization
    )
    return record


def _generate_test_keypair():
    """Generate an ephemeral Ed25519 keypair for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = Ed25519PrivateKey.generate()
    return priv, serialization


class TestUnsignedV2Record(unittest.TestCase):
    """Unsigned v2 records must verify (backward compatibility)."""

    def test_unsigned_record_passes(self):
        rec = _make_unsigned_v2_record()
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 0, f"Expected pass, got: {lines}")
        self.assertTrue(any("PASS" in l for l in lines))

    def test_unsigned_record_via_verify_record_dict(self):
        rec = _make_unsigned_v2_record()
        rc, lines = verify_record_dict(rec)
        self.assertEqual(rc, 0, f"Expected pass, got: {lines}")

    def test_tampered_unsigned_record_fails(self):
        rec = _make_unsigned_v2_record()
        rec["policy_decision"] = "DENY"  # tamper
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 1)
        self.assertTrue(any("mismatch" in l for l in lines))


class TestSignedV2Record(unittest.TestCase):
    """Signed v2 records must verify hash + signature."""

    def setUp(self):
        self.priv, self.ser = _generate_test_keypair()
        # Write the key to a temp file for the verifier to load
        self._key_dir = tempfile.mkdtemp()
        key_path = Path(self._key_dir) / "test.key"
        key_path.write_bytes(self.priv.private_bytes(
            encoding=self.ser.Encoding.PEM,
            format=self.ser.PrivateFormat.PKCS8,
            encryption_algorithm=self.ser.NoEncryption(),
        ))
        self._orig_signing_path = os.environ.get("GOV_SIGNING_KEY_PATH")
        self._orig_verify_path = os.environ.get("GOV_VERIFY_KEY_PATH")
        os.environ["GOV_SIGNING_KEY_PATH"] = str(key_path)
        os.environ.pop("GOV_VERIFY_KEY_PATH", None)

    def tearDown(self):
        if self._orig_signing_path is not None:
            os.environ["GOV_SIGNING_KEY_PATH"] = self._orig_signing_path
        else:
            os.environ.pop("GOV_SIGNING_KEY_PATH", None)
        if self._orig_verify_path is not None:
            os.environ["GOV_VERIFY_KEY_PATH"] = self._orig_verify_path
        else:
            os.environ.pop("GOV_VERIFY_KEY_PATH", None)
        import shutil
        shutil.rmtree(self._key_dir, ignore_errors=True)

    def test_signed_record_passes(self):
        rec = _make_signed_v2_record(self.priv, self.ser)
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 0, f"Expected pass, got: {lines}")
        self.assertTrue(any("signature verified" in l for l in lines))

    def test_signed_record_via_verify_record_dict(self):
        rec = _make_signed_v2_record(self.priv, self.ser)
        rc, lines = verify_record_dict(rec)
        self.assertEqual(rc, 0, f"Expected pass, got: {lines}")

    def test_tampered_signed_record_fails_hash(self):
        rec = _make_signed_v2_record(self.priv, self.ser)
        rec["policy_decision"] = "DENY"  # tamper after signing
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 1)
        self.assertTrue(any("mismatch" in l for l in lines))

    def test_tampered_signature_fails(self):
        rec = _make_signed_v2_record(self.priv, self.ser)
        # Corrupt the signature by flipping a character in the middle.
        # NOTE: Do not flip the last character — for 64-byte payloads the
        # last base64url char only has 2 significant bits (positions 5-4),
        # and swapping between chars in the same 16-value group (e.g. A↔B)
        # produces identical decoded bytes (a no-op tamper).
        sig = rec["signature"]
        mid = len(sig) // 2
        ch = sig[mid]
        flip = "A" if ch != "A" else "B"
        rec["signature"] = sig[:mid] + flip + sig[mid + 1:]
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 1)
        self.assertTrue(any("signature" in l.lower() for l in lines))

    def test_incomplete_signature_fields_fails(self):
        rec = _make_signed_v2_record(self.priv, self.ser)
        rec["signing_key_id"] = None  # incomplete: sig present but key_id null
        # Re-hash since we changed a field
        rec["record_hash"] = _compute_v2_hash(rec)
        rc, lines = _verify_v2_mediated_decision(rec)
        self.assertEqual(rc, 1)
        self.assertTrue(any("incomplete" in l.lower() for l in lines))


class TestMixedChain(unittest.TestCase):
    """Mixed chain: unsigned records followed by signed records."""

    def setUp(self):
        self.priv, self.ser = _generate_test_keypair()
        self._key_dir = tempfile.mkdtemp()
        key_path = Path(self._key_dir) / "test.key"
        key_path.write_bytes(self.priv.private_bytes(
            encoding=self.ser.Encoding.PEM,
            format=self.ser.PrivateFormat.PKCS8,
            encryption_algorithm=self.ser.NoEncryption(),
        ))
        self._orig_signing_path = os.environ.get("GOV_SIGNING_KEY_PATH")
        self._orig_verify_path = os.environ.get("GOV_VERIFY_KEY_PATH")
        os.environ["GOV_SIGNING_KEY_PATH"] = str(key_path)
        os.environ.pop("GOV_VERIFY_KEY_PATH", None)

    def tearDown(self):
        if self._orig_signing_path is not None:
            os.environ["GOV_SIGNING_KEY_PATH"] = self._orig_signing_path
        else:
            os.environ.pop("GOV_SIGNING_KEY_PATH", None)
        if self._orig_verify_path is not None:
            os.environ["GOV_VERIFY_KEY_PATH"] = self._orig_verify_path
        else:
            os.environ.pop("GOV_VERIFY_KEY_PATH", None)
        import shutil
        shutil.rmtree(self._key_dir, ignore_errors=True)

    def test_mixed_chain_all_verify(self):
        """Simulate a chain: 3 unsigned records, then 3 signed records."""
        chain = []

        # Unsigned records (pre-dispatch era)
        for i in range(3):
            prev_hash = chain[-1]["record_hash"] if chain else None
            rec = _make_unsigned_v2_record(
                request_id=f"req-{i:03d}",
                prev_record_hash=prev_hash,
            )
            chain.append(rec)

        # Signed records (post-dispatch era)
        for i in range(3, 6):
            prev_hash = chain[-1]["record_hash"] if chain else None
            rec = _make_signed_v2_record(
                self.priv, self.ser,
                request_id=f"req-{i:03d}",
                prev_record_hash=prev_hash,
            )
            chain.append(rec)

        # Every record must verify individually
        for i, rec in enumerate(chain):
            rc, lines = verify_record_dict(rec)
            self.assertEqual(rc, 0, f"Record {i} failed: {lines}")

        # Chain linkage must hold
        for i in range(1, len(chain)):
            self.assertEqual(
                chain[i]["prev_record_hash"],
                chain[i - 1]["record_hash"],
                f"Chain break at record {i}",
            )

    def test_unsigned_after_signed_still_verifies(self):
        """Even if an unsigned record appears after signed ones, it still verifies
        (the verifier doesn't enforce monotonic signing — it just validates what's there)."""
        signed = _make_signed_v2_record(self.priv, self.ser)
        unsigned = _make_unsigned_v2_record(
            prev_record_hash=signed["record_hash"],
            request_id="req-late-unsigned",
        )
        rc1, lines1 = verify_record_dict(signed)
        rc2, lines2 = verify_record_dict(unsigned)
        self.assertEqual(rc1, 0, f"Signed failed: {lines1}")
        self.assertEqual(rc2, 0, f"Unsigned failed: {lines2}")


if __name__ == "__main__":
    unittest.main()
