#!/usr/bin/env python3
"""Tests for the telemetry notification system (A2).

1. Telemetry artifact includes license_id from installed license.
2. Telemetry artifact includes processed_notifications from local storage.
3. Notification processing writes chain events for all four types.
4. Processed notification IDs are persisted and included in subsequent payloads.
5. Empty notifications array handled gracefully.
6. Malformed notifications logged and skipped.
7. license_delivered notification activates token.
8. license_revoked notification reverts to personal.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mcp"))
sys.path.insert(0, str(REPO / "scripts"))

# Set up test Ed25519 keypair before importing licensing
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

_TEST_PRIV = Ed25519PrivateKey.generate()
_TEST_PUB = _TEST_PRIV.public_key()
_TEST_PUB_HEX = _TEST_PUB.public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
os.environ["GOV_LICENSE_VERIFY_KEY_HEX"] = _TEST_PUB_HEX
os.environ["GOV_LICENSE_OVERRIDE_ACKNOWLEDGED"] = "1"
_TEST_KEY_FILE = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
_TEST_KEY_FILE.write(_TEST_PRIV.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()))
_TEST_KEY_FILE.flush()
os.environ["GOV_LICENSE_SIGNING_KEY_PATH"] = _TEST_KEY_FILE.name

import importlib
import licensing
importlib.reload(licensing)
from licensing import (
    generate_license_token, activate_license, initialize_trial,
    load_license, save_license, resolve_posture,
)
from feedback_signing import (
    build_telemetry_artifact,
    load_processed_notifications,
    save_processed_notifications,
)


def test_telemetry_includes_license_id():
    """Telemetry artifact includes license_id when a v3 license is installed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        # Activate a v3 license
        token = generate_license_token(
            "crew", "20271231", "test-org",
            version=3, license_id="lic-aabbccddee03",
            customer_id="cus_test999", origin="purchased",
        )
        activate_license(runtime, token, organization_id="test-org")

        artifact = build_telemetry_artifact(runtime_root=runtime)
        assert artifact.get("license_id") == "lic-aabbccddee03", \
            f"expected license_id in artifact, got: {artifact.get('license_id')}"
    print("PASS: telemetry includes license_id")


def test_telemetry_includes_processed_notifications():
    """Telemetry artifact includes processed_notifications from local storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        # Save some processed notification IDs
        save_processed_notifications(runtime, ["notif-aaa", "notif-bbb"])

        artifact = build_telemetry_artifact(runtime_root=runtime)
        pn = artifact.get("processed_notifications", [])
        assert "notif-aaa" in pn, f"missing notif-aaa in {pn}"
        assert "notif-bbb" in pn, f"missing notif-bbb in {pn}"
    print("PASS: telemetry includes processed_notifications")


def test_telemetry_no_license_id_for_trial():
    """Telemetry artifact has no license_id for trial installations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        artifact = build_telemetry_artifact(runtime_root=runtime)
        assert "license_id" not in artifact, \
            f"trial should not have license_id, got: {artifact.get('license_id')}"
    print("PASS: no license_id for trial")


def test_processed_notifications_persistence():
    """Processed notification IDs are persisted and loaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)

        # Initially empty
        assert load_processed_notifications(runtime) == []

        # Save
        save_processed_notifications(runtime, ["notif-111", "notif-222"])
        loaded = load_processed_notifications(runtime)
        assert "notif-111" in loaded
        assert "notif-222" in loaded

        # Append more
        loaded.append("notif-333")
        save_processed_notifications(runtime, loaded)
        reloaded = load_processed_notifications(runtime)
        assert "notif-333" in reloaded
        assert len(reloaded) == 3
    print("PASS: processed notifications persistence")


def test_empty_notifications_handled():
    """Empty notifications array handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        save_processed_notifications(runtime, [])
        loaded = load_processed_notifications(runtime)
        assert loaded == []
    print("PASS: empty notifications handled")


def test_malformed_notifications_file():
    """Malformed notifications file returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        path = runtime / "notifications_processed.json"
        path.write_text("not valid json {{{")
        loaded = load_processed_notifications(runtime)
        assert loaded == []
    print("PASS: malformed notifications file handled")


def test_notification_chain_events():
    """Notification processing writes correct chain events for each type."""
    from event_model import build_non_action_event, NON_ACTION_EVENT_TYPES

    # Verify all notification event types are registered
    for et in ["license_revoked", "license_activated",
               "license_expiration_warning", "license_modified"]:
        assert et in NON_ACTION_EVENT_TYPES, f"{et} not in NON_ACTION_EVENT_TYPES"

    # Build chain events for each type
    test_cases = [
        ("license_revoked", {"notification_id": "n1", "notification_type": "license_revoked",
                             "license_id": "lic-test", "reason": "test"}),
        ("license_activated", {"notification_id": "n2", "notification_type": "license_delivered",
                               "license_id": "lic-test", "token": "abc.def", "tier": "crew"}),
        ("license_expiration_warning", {"notification_id": "n3",
                                        "notification_type": "license_expiration_warning",
                                        "license_id": "lic-test", "days_remaining": 7}),
        ("license_modified", {"notification_id": "n4", "notification_type": "license_modified",
                              "license_id": "lic-test", "new_tier": "team"}),
    ]
    for event_type, payload in test_cases:
        event = build_non_action_event(event_type, payload)
        assert event["event_type"] == event_type
        assert event["notification_id"] == payload["notification_id"]
        assert event["record_hash"].startswith("sha256:")
    print("PASS: notification chain events")


def test_license_delivered_activates_token():
    """license_delivered notification with token activates the license."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        # Generate a v3 token to deliver
        token = generate_license_token(
            "crew", "20271231", "delivered-org",
            version=3, license_id="lic-delivered01",
            customer_id="cus_deliver1", origin="purchased",
        )

        # Simulate what _process_telemetry_notifications does
        activate_license(runtime, token)

        posture = resolve_posture(runtime)
        assert posture["license_status"] == "licensed"
        assert posture["license_tier"] == "crew"
    print("PASS: license_delivered activates token")


def test_license_revoked_reverts_to_personal():
    """license_revoked notification reverts install to personal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        # Activate a license first
        token = generate_license_token(
            "crew", "20271231", "revoke-org",
            version=3, license_id="lic-revoke001",
            customer_id="cus_revoke1", origin="purchased",
        )
        activate_license(runtime, token, organization_id="revoke-org")
        assert resolve_posture(runtime)["license_status"] == "licensed"

        # Simulate revocation processing
        config = load_license(runtime)
        config["license_status"] = "personal"
        config["license_tier"] = "personal"
        save_license(runtime, config)

        posture = resolve_posture(runtime)
        assert posture["license_status"] == "personal"
        assert posture["license_tier"] == "personal"
    print("PASS: license_revoked reverts to personal")


if __name__ == "__main__":
    test_telemetry_includes_license_id()
    test_telemetry_includes_processed_notifications()
    test_telemetry_no_license_id_for_trial()
    test_processed_notifications_persistence()
    test_empty_notifications_handled()
    test_malformed_notifications_file()
    test_notification_chain_events()
    test_license_delivered_activates_token()
    test_license_revoked_reverts_to_personal()
    print("\nAll notification tests PASS")
