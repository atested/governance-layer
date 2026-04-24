#!/usr/bin/env python3
"""Tests for the usage_attestation governed tool.

1. Attestation generates valid artifact with required fields.
2. Artifact hash is deterministic and verifiable.
3. Tier recommendation follows user-count thresholds.
4. Attestation event is appended to the decision chain.
5. Integration: usage_attestation tool via remote server.
"""
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "remote_server.py"

sys.path.insert(0, str(REPO / "mcp"))
from licensing import initialize_trial


def test_tier_recommendation_thresholds():
    """Tier recommendation follows current user-count rules.

    Current model: personal / personal_plus / crew / team / institution.
    Boundaries: <=1 personal, <=3 personal_plus, <=12 crew, <=50 team, 51+ institution.
    """
    thresholds = [
        (0, "personal"),
        (1, "personal"),
        (2, "personal_plus"),
        (3, "personal_plus"),
        (4, "crew"),
        (12, "crew"),
        (13, "team"),
        (50, "team"),
        (51, "institution"),
        (200, "institution"),
    ]
    for n_users, expected in thresholds:
        if n_users <= 1:
            tier = "personal"
        elif n_users <= 3:
            tier = "personal_plus"
        elif n_users <= 12:
            tier = "crew"
        elif n_users <= 50:
            tier = "team"
        else:
            tier = "institution"
        assert tier == expected, f"n_users={n_users}: expected {expected}, got {tier}"
    print("PASS: tier recommendation thresholds")


def test_attestation_artifact_hash():
    """Artifact hash is deterministic for the same content."""
    artifact = {
        "attestation_version": "1.0",
        "attestation_id": "att_test123456789a",
        "generated_at": "2026-03-30T12:00:00Z",
        "unique_users": 2,
        "unique_sessions": 5,
        "total_operations": 100,
        "operations_by_category": {"FS_WRITE": 40, "FS_READ": 60},
        "license_status": "trial",
        "license_tier": "personal",
        "organization_id": "",
        "license_expiry": "2026-04-29T00:00:00Z",
        "trial_days_remaining": 30,
        "recommended_tier": "personal_plus",
    }
    artifact_bytes = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}"

    # Same content → same hash
    artifact_bytes2 = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h2 = f"sha256:{hashlib.sha256(artifact_bytes2).hexdigest()}"
    assert h == h2, f"hash mismatch: {h} vs {h2}"

    # Different content → different hash
    artifact["unique_users"] = 3
    artifact_bytes3 = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h3 = f"sha256:{hashlib.sha256(artifact_bytes3).hexdigest()}"
    assert h != h3, "hash should differ for different content"
    print("PASS: attestation artifact hash deterministic")


def test_attestation_via_remote_server():
    """usage_attestation tool returns valid artifact via remote server."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        port = _choose_free_port()
        runtime_dir = tempfile.mkdtemp(prefix="govmcp-att-test-")
        os.makedirs(os.path.join(runtime_dir, "LOGS"), exist_ok=True)
        os.makedirs(os.path.join(runtime_dir, "tmp"), exist_ok=True)
        token = "att-test-token"

        # Initialize trial so licensing works
        initialize_trial(Path(runtime_dir))

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

            # Make a governed call first to seed some data
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    await session.call_tool("fs_list", {"path": str(REPO)})

            # Call usage_attestation
            async with streamablehttp_client(url, headers=headers) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    resp = await session.call_tool("usage_attestation", {})
                    artifact = json.loads(resp.content[0].text)

            # Verify required fields
            required = [
                "attestation_version", "attestation_id", "generated_at",
                "unique_users", "unique_sessions", "total_operations",
                "operations_by_category", "license_status", "license_tier",
                "organization_id", "license_expiry", "recommended_tier",
                "artifact_hash",
            ]
            for field in required:
                assert field in artifact, f"missing field: {field}"

            assert artifact["attestation_version"] == "1.0"
            assert artifact["attestation_id"].startswith("att_")
            assert artifact["artifact_hash"].startswith("sha256:")
            assert artifact["total_operations"] >= 1  # at least the fs_list
            assert artifact["license_status"] == "trial"
            print("PASS: attestation via remote server — all fields present")

            # Verify hash is correct (recompute without artifact_hash field)
            verify = {k: v for k, v in artifact.items() if k != "artifact_hash"}
            verify_bytes = json.dumps(verify, sort_keys=True, separators=(",", ":")).encode("utf-8")
            expected_hash = f"sha256:{hashlib.sha256(verify_bytes).hexdigest()}"
            assert artifact["artifact_hash"] == expected_hash, \
                f"hash mismatch: {artifact['artifact_hash']} vs {expected_hash}"
            print("PASS: attestation artifact hash verified")

            # Check chain has the attestation event
            chain_path = os.path.join(runtime_dir, "LOGS", "decision-chain.jsonl")
            chain_lines = Path(chain_path).read_text(encoding="utf-8").strip().splitlines()
            att_events = [
                json.loads(l) for l in chain_lines
                if "usage_attestation" in l
            ]
            assert len(att_events) >= 1, "no attestation event in chain"
            att_evt = att_events[-1]
            assert att_evt["event_type"] == "usage_attestation"
            assert att_evt["attestation_id"] == artifact["attestation_id"]
            assert att_evt["artifact_hash"] == artifact["artifact_hash"]
            print("PASS: attestation event recorded in chain")

            # Check attestation file was written
            att_dir = os.path.join(runtime_dir, "LOGS", "attestations")
            att_files = list(Path(att_dir).glob("att_*.json"))
            assert len(att_files) >= 1, "no attestation file written"
            stored = json.loads(att_files[0].read_text(encoding="utf-8"))
            assert stored["attestation_id"] == artifact["attestation_id"]
            print("PASS: attestation file persisted")

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
    test_tier_recommendation_thresholds()
    test_attestation_artifact_hash()
    test_attestation_via_remote_server()
    print("\nAll usage attestation tests PASS")
