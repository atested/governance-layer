"""Tests for F-11: Sign all chain events.

Verifies:
  1. build_non_action_event produces signed events when given a signing key
  2. sign_non_action_event produces valid Ed25519 signatures
  3. ApprovalStore rejects unsigned events when require_signatures=True
  4. ApprovalStore rejects tampered-signature events
  5. ApprovalStore accepts properly signed events
  6. ApprovalStore backward compatibility (require_signatures=False)
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "mcp"))

from event_model import build_non_action_event, sign_non_action_event, canonical_json
from approval_store import ApprovalStore, load_approval_store_from_events, _verify_event_signature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ed25519_keypair():
    """Generate a fresh Ed25519 keypair for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    import hashlib
    key_id = "ed25519:" + hashlib.sha256(raw).hexdigest()
    return priv, pub, key_id


def _make_approval_event(signing_key=None, signing_key_id=None):
    """Build a signed opaque_artifact_approval event."""
    return build_non_action_event(
        "opaque_artifact_approval",
        {
            "artifact_identity": "sha256:abc123",
            "approving_operator": "test-operator",
            "governed_family": "test-family",
            "deployment_context": "test-context",
            "policy_version": "v1",
        },
        signing_key=signing_key,
        signing_key_id=signing_key_id,
    )


def _make_revocation_event(signing_key=None, signing_key_id=None):
    """Build a signed opaque_artifact_revocation event."""
    return build_non_action_event(
        "opaque_artifact_revocation",
        {
            "artifact_identity": "sha256:abc123",
            "revoking_operator": "test-operator",
            "governed_family": "test-family",
            "deployment_context": "test-context",
            "policy_version": "v1",
        },
        signing_key=signing_key,
        signing_key_id=signing_key_id,
    )


# ---------------------------------------------------------------------------
# Event signing tests
# ---------------------------------------------------------------------------

class TestEventSigning:
    def test_build_non_action_event_unsigned(self):
        """Without signing key, signature and signing_key_id are None."""
        event = build_non_action_event(
            "verification_state_transition",
            {"governed_family": "test", "from_state": "unverified", "to_state": "verified"},
        )
        assert event["signature"] is None
        assert event["signing_key_id"] is None
        assert event["record_hash"].startswith("sha256:")

    def test_build_non_action_event_signed(self, ed25519_keypair):
        """With signing key, event has a valid signature."""
        priv, pub, key_id = ed25519_keypair
        event = build_non_action_event(
            "verification_state_transition",
            {"governed_family": "test", "from_state": "unverified", "to_state": "verified"},
            signing_key=priv,
            signing_key_id=key_id,
        )
        assert event["signature"] is not None
        assert event["signing_key_id"] == key_id
        # Verify signature
        assert _verify_event_signature(event, pub)

    def test_sign_non_action_event_standalone(self, ed25519_keypair):
        """sign_non_action_event can sign an already-built event."""
        priv, pub, key_id = ed25519_keypair
        event = build_non_action_event(
            "usage_attestation",
            {"summary": "test"},
        )
        assert event["signature"] is None
        sign_non_action_event(event, priv, key_id)
        assert event["signature"] is not None
        assert _verify_event_signature(event, pub)

    def test_tampered_event_fails_verification(self, ed25519_keypair):
        """Modifying a signed event makes the signature invalid."""
        priv, pub, key_id = ed25519_keypair
        event = build_non_action_event(
            "verification_state_transition",
            {"governed_family": "test", "from_state": "unverified", "to_state": "verified"},
            signing_key=priv,
            signing_key_id=key_id,
        )
        # Tamper with the event
        event["governed_family"] = "tampered"
        assert not _verify_event_signature(event, pub)


# ---------------------------------------------------------------------------
# ApprovalStore signature verification tests
# ---------------------------------------------------------------------------

class TestApprovalStoreSignatureVerification:
    def test_unsigned_approval_rejected_when_required(self, ed25519_keypair):
        """Unsigned approval events are rejected when require_signatures=True."""
        _, pub, _ = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)
        event = _make_approval_event()  # unsigned
        accepted = store.ingest_approval(event)
        assert accepted is False
        assert store.rejected_count == 1
        assert len(store.all_approvals()) == 0

    def test_signed_approval_accepted(self, ed25519_keypair):
        """Properly signed approval events are accepted."""
        priv, pub, key_id = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)
        event = _make_approval_event(signing_key=priv, signing_key_id=key_id)
        accepted = store.ingest_approval(event)
        assert accepted is True
        assert store.rejected_count == 0
        assert len(store.all_approvals()) == 1

    def test_tampered_approval_rejected(self, ed25519_keypair):
        """Tampered approval events are rejected."""
        priv, pub, key_id = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)
        event = _make_approval_event(signing_key=priv, signing_key_id=key_id)
        event["approving_operator"] = "evil-operator"
        accepted = store.ingest_approval(event)
        assert accepted is False
        assert store.rejected_count == 1

    def test_unsigned_revocation_rejected_when_required(self, ed25519_keypair):
        """Unsigned revocation events are rejected when require_signatures=True."""
        priv, pub, key_id = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)
        # First add a valid approval
        approval = _make_approval_event(signing_key=priv, signing_key_id=key_id)
        store.ingest_approval(approval)
        assert len(store.all_approvals()) == 1
        # Try unsigned revocation — should be rejected
        revocation = _make_revocation_event()  # unsigned
        accepted = store.ingest_revocation(revocation)
        assert accepted is False
        # Approval should still be present
        assert len(store.all_approvals()) == 1

    def test_signed_revocation_accepted(self, ed25519_keypair):
        """Properly signed revocation removes the approval."""
        priv, pub, key_id = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)
        approval = _make_approval_event(signing_key=priv, signing_key_id=key_id)
        store.ingest_approval(approval)
        assert len(store.all_approvals()) == 1
        revocation = _make_revocation_event(signing_key=priv, signing_key_id=key_id)
        accepted = store.ingest_revocation(revocation)
        assert accepted is True
        assert len(store.all_approvals()) == 0

    def test_backward_compat_no_signatures_required(self):
        """Default mode accepts unsigned events (backward compatibility)."""
        store = ApprovalStore()
        event = _make_approval_event()
        accepted = store.ingest_approval(event)
        assert accepted is True
        assert len(store.all_approvals()) == 1

    def test_load_from_events_with_signatures(self, ed25519_keypair):
        """load_approval_store_from_events respects require_signatures."""
        priv, pub, key_id = ed25519_keypair
        signed = _make_approval_event(signing_key=priv, signing_key_id=key_id)
        unsigned = _make_approval_event()
        unsigned["artifact_identity"] = "sha256:different"
        store = load_approval_store_from_events(
            [signed, unsigned],
            require_signatures=True,
            public_key=pub,
        )
        # Only the signed event should be ingested
        assert len(store.all_approvals()) == 1
        assert store.rejected_count == 1
        assert store.all_approvals()[0]["artifact_identity"] == "sha256:abc123"
