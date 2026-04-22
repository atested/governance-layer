#!/usr/bin/env python3
"""
Tests for the licensing posture system.

1. New installation defaults to trial with 30-day expiry.
2. Governance records during trial include license_status=trial.
3. Governance records after trial expiry include license_status=unlicensed (no lockout).
4. License activation changes status to licensed with correct tier.
5. Personal single-user detection works correctly.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "remote_server.py"

# Add mcp/ to path so we can import licensing directly
sys.path.insert(0, str(REPO / "mcp"))
from licensing import (
    generate_license_token,
    validate_license_key,
    resolve_posture,
    initialize_trial,
    load_license,
    save_license,
    activate_license,
    trial_days_remaining,
    TRIAL_DAYS,
)

# For tests, we need a real Ed25519 keypair.
# Generate ephemeral test keypair and override the verify key.
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

_TEST_PRIV = Ed25519PrivateKey.generate()
_TEST_PUB = _TEST_PRIV.public_key()
_TEST_PUB_HEX = _TEST_PUB.public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
# Override verify key so tokens signed by our test key are accepted.
os.environ["GOV_LICENSE_VERIFY_KEY_HEX"] = _TEST_PUB_HEX
# Write test private key to a temp file for generate_license_token.
_TEST_KEY_FILE = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
_TEST_KEY_FILE.write(_TEST_PRIV.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()))
_TEST_KEY_FILE.flush()
os.environ["GOV_LICENSE_SIGNING_KEY_PATH"] = _TEST_KEY_FILE.name
# Re-import to pick up the new verify key
import importlib
import licensing
importlib.reload(licensing)
from licensing import (
    generate_license_token,
    validate_license_key,
    resolve_posture,
    initialize_trial,
    load_license,
    save_license,
    activate_license,
    trial_days_remaining,
    TRIAL_DAYS,
)


def test_license_key_scheme():
    """License token generation and validation round-trip (Ed25519 v2)."""
    token = generate_license_token("team", "20270101", "acme")
    assert "." in token, token
    decoded = validate_license_key(token)
    assert decoded is not None, f"valid token rejected: {token}"
    assert decoded["tier"] == "team"
    assert decoded["expiry_date"] == "20270101"

    # Legacy keys must be rejected (C1 fix)
    assert validate_license_key("GOV-team-20270101-00000000") is None
    assert validate_license_key("GOV-team-20270101-abcdef12") is None
    assert validate_license_key("BAD-team-20270101-abcdef12") is None
    assert validate_license_key("") is None
    # Tampered token
    assert validate_license_key(token + "X") is None
    print("PASS: license key scheme (Ed25519 v2)")


def test_trial_initialization():
    """New installation defaults to trial with 30-day expiry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        posture = resolve_posture(runtime)

        assert posture["license_status"] == "trial", posture
        assert posture["license_tier"] == "personal", posture
        assert posture["organization_id"] == "", posture
        assert posture["license_expiry"] != "", posture

        # Verify expiry is approximately 30 days from now
        expiry = datetime.fromisoformat(posture["license_expiry"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (expiry - now).days
        assert 29 <= diff <= 30, f"expected ~30 days, got {diff}"

        remaining = trial_days_remaining(runtime)
        assert remaining is not None
        assert 29 <= remaining <= 30, f"expected ~30, got {remaining}"
    print("PASS: trial initialization")


def test_trial_expiry_unlicensed():
    """After trial expiry with no license: status becomes unlicensed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)

        # Create a trial that expired yesterday
        expired_config = {
            "license_status": "trial",
            "license_tier": "personal",
            "organization_id": "",
            "license_expiry": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
            "trial_started": (datetime.now(timezone.utc) - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license_key": "",
        }
        save_license(runtime, expired_config)

        # Resolve with >1 user (not personal)
        posture = resolve_posture(runtime, unique_user_count=3)
        assert posture["license_status"] == "unlicensed", posture
    print("PASS: trial expiry → unlicensed")


def test_trial_expiry_personal():
    """After trial expiry with single user and no license: becomes personal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)

        expired_config = {
            "license_status": "trial",
            "license_tier": "personal",
            "organization_id": "",
            "license_expiry": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
            "trial_started": (datetime.now(timezone.utc) - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license_key": "",
        }
        save_license(runtime, expired_config)

        posture = resolve_posture(runtime, unique_user_count=1)
        assert posture["license_status"] == "personal", posture
    print("PASS: trial expiry + single user → personal")


def test_license_activation():
    """License activation changes status to licensed with correct tier."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        token = generate_license_token("business", "20271231", "acme")
        result = activate_license(runtime, token, organization_id="acme-corp")
        assert result["ok"] is True, result
        assert result["license_status"] == "licensed"
        assert result["license_tier"] == "business"
        assert result["organization_id"] == "acme-corp"

        # Verify persisted state
        posture = resolve_posture(runtime)
        assert posture["license_status"] == "licensed"
        assert posture["license_tier"] == "business"
        assert posture["organization_id"] == "acme-corp"
    print("PASS: license activation")


def test_license_key_scheme_v3():
    """License token generation and validation round-trip (Ed25519 v3)."""
    token = generate_license_token(
        "crew", "20270601", "acme",
        version=3, license_id="lic-abc123def456",
        customer_id="cus_test123", origin="purchased",
    )
    assert "." in token, token
    decoded = validate_license_key(token)
    assert decoded is not None, f"valid v3 token rejected: {token}"
    assert decoded["tier"] == "crew"
    assert decoded["expiry_date"] == "20270601"
    assert decoded["organization"] == "acme"
    assert decoded["version"] == 3
    assert decoded["license_id"] == "lic-abc123def456"
    assert decoded["customer_id"] == "cus_test123"
    assert decoded["origin"] == "purchased"
    print("PASS: license key scheme (Ed25519 v3)")


def test_v2_v3_backward_compatibility():
    """v2 tokens still validate after v3 support is added."""
    v2_token = generate_license_token("team", "20270101", "acme")
    v3_token = generate_license_token(
        "personal_plus", "20270601", "solo",
        version=3, license_id="lic-aabbccddee01",
        customer_id="cus_v3test", origin="purchased",
    )

    # Both validate
    v2_decoded = validate_license_key(v2_token)
    v3_decoded = validate_license_key(v3_token)
    assert v2_decoded is not None
    assert v3_decoded is not None

    # v2 has version=2, no v3 fields
    assert v2_decoded["version"] == 2
    assert "license_id" not in v2_decoded
    assert "customer_id" not in v2_decoded
    assert "origin" not in v2_decoded

    # v3 has version=3 with v3 fields
    assert v3_decoded["version"] == 3
    assert v3_decoded["license_id"] == "lic-aabbccddee01"
    assert v3_decoded["customer_id"] == "cus_v3test"
    assert v3_decoded["origin"] == "purchased"

    # Tampered tokens still rejected
    assert validate_license_key(v2_token + "X") is None
    assert validate_license_key(v3_token + "X") is None
    print("PASS: v2/v3 backward compatibility")


def test_v3_new_tiers():
    """v3 tier names (personal_plus, crew, institution) are accepted."""
    for tier in ("personal_plus", "crew", "institution"):
        token = generate_license_token(
            tier, "20270601", "test",
            version=3, license_id="lic-000000000000",
            customer_id="", origin="granted",
        )
        decoded = validate_license_key(token)
        assert decoded is not None, f"tier {tier} rejected"
        assert decoded["tier"] == tier
    # Legacy tier names still work
    for tier in ("business", "enterprise"):
        token = generate_license_token(tier, "20270601", "test")
        decoded = validate_license_key(token)
        assert decoded is not None, f"legacy tier {tier} rejected"
    print("PASS: v3 new tier names accepted")


def test_v3_activation():
    """v3 tokens activate correctly and preserve v3 fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        token = generate_license_token(
            "crew", "20271231", "acme-crew",
            version=3, license_id="lic-aabbccddee02",
            customer_id="cus_crew1", origin="purchased",
        )
        result = activate_license(runtime, token, organization_id="acme-crew")
        assert result["ok"] is True, result
        assert result["license_status"] == "licensed"
        assert result["license_tier"] == "crew"

        posture = resolve_posture(runtime)
        assert posture["license_status"] == "licensed"
        assert posture["license_tier"] == "crew"
    print("PASS: v3 activation")


def test_invalid_activation():
    """Invalid license key is rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = Path(tmpdir)
        initialize_trial(runtime)

        result = activate_license(runtime, "INVALID-KEY")
        assert result["ok"] is False
        assert "INVALID_LICENSE_KEY" in result.get("error", "")

        # Status unchanged
        posture = resolve_posture(runtime)
        assert posture["license_status"] == "trial"
    print("PASS: invalid activation rejected")


def test_posture_in_governed_records():
    """Governance records from a remote server include licensing fields."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        port = _choose_free_port()
        runtime_dir = tempfile.mkdtemp(prefix="govmcp-license-test-")
        os.makedirs(os.path.join(runtime_dir, "LOGS"), exist_ok=True)
        os.makedirs(os.path.join(runtime_dir, "tmp"), exist_ok=True)
        token = "license-test-token"

        env = os.environ.copy()
        env["GOV_RUNTIME_DIR"] = runtime_dir
        env["GOV_CANONICAL_REPO_PATH"] = str(REPO)
        env["GOV_RUNTIME_PATH"] = runtime_dir
        env["GOVMCP_HOST"] = "127.0.0.1"
        env["GOVMCP_PORT"] = str(port)
        env["GOVMCP_STREAMABLE_HTTP_PATH"] = "/mcp"
        env["GOVMCP_LOG_LEVEL"] = "ERROR"
        env["GOVMCP_REMOTE_AUTH_TOKEN"] = token

        proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            headers = {"Authorization": f"Bearer {token}"}

            # Wait for server
            for _ in range(50):
                if proc.poll() is not None:
                    out, err = proc.communicate()
                    raise AssertionError(f"server exited early: {out!r} {err!r}")
                try:
                    async with streamablehttp_client(url, headers=headers) as (r, w, _):
                        async with ClientSession(r, w) as session:
                            await session.initialize()
                            break
                except Exception:
                    await asyncio.sleep(0.2)

            # Make a governed call
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    resp = await session.call_tool("fs_list", {"path": str(REPO)})
                    payload = json.loads(resp.content[0].text)

            rec = payload.get("decision_record", {})
            assert rec.get("license_status") == "trial", f"expected trial, got: {rec.get('license_status')}"
            assert rec.get("license_tier") == "personal", rec.get("license_tier")
            assert "license_expiry" in rec, f"missing license_expiry: {rec.keys()}"
            assert "organization_id" in rec, f"missing organization_id: {rec.keys()}"
            print("PASS: licensing posture in governed records")

            # Test license_status tool
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    resp = await session.call_tool("license_status", {})
                    status = json.loads(resp.content[0].text)
            assert status.get("license_status") == "trial", status
            assert status.get("trial_days_remaining") is not None, status
            print("PASS: license_status tool")

            # Test license_activate tool
            token = generate_license_token("team", "20271231", "test-org")
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    resp = await session.call_tool("license_activate", {"license_key": token, "organization_id": "test-org"})
                    result = json.loads(resp.content[0].text)
            assert result.get("ok") is True, result
            assert result.get("license_tier") == "team", result
            print("PASS: license_activate tool")

            # Verify next governed call shows licensed
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    resp = await session.call_tool("fs_list", {"path": str(REPO)})
                    payload = json.loads(resp.content[0].text)
            rec = payload.get("decision_record", {})
            assert rec.get("license_status") == "licensed", f"expected licensed, got: {rec.get('license_status')}"
            assert rec.get("license_tier") == "team", rec.get("license_tier")
            print("PASS: post-activation governed records show licensed")

        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    asyncio.run(_run())


def _choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    test_license_key_scheme()
    test_license_key_scheme_v3()
    test_v2_v3_backward_compatibility()
    test_v3_new_tiers()
    test_v3_activation()
    test_trial_initialization()
    test_trial_expiry_unlicensed()
    test_trial_expiry_personal()
    test_license_activation()
    test_invalid_activation()
    test_posture_in_governed_records()
    print("\nAll licensing tests PASS")
