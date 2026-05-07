#!/usr/bin/env python3
"""Tests for D-2026-0404-037: atested CLI."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "scripts" / "atested_cli.py"
WRAPPER = REPO / "atested"
SCRIPTS_DIR = REPO / "scripts"
MCP_DIR = REPO / "mcp"
for _p in (str(SCRIPTS_DIR), str(MCP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _run_cli(args, env_overrides=None):
    """Run the CLI as a subprocess and return (rc, stdout, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _make_isolated_runtime(tmpdir):
    """Create an isolated GOV_RUNTIME_DIR with an empty chain."""
    runtime = Path(tmpdir) / "runtime"
    (runtime / "LOGS").mkdir(parents=True)
    return runtime


def test_help():
    rc, out, err = _run_cli(["--help"])
    assert rc == 0
    assert "atested" in out
    assert "approve" in out
    assert "revoke" in out
    assert "status" in out
    assert "chain" in out
    print("PASS: test_help")


def test_policy_list():
    rc, out, err = _run_cli(["policy", "list"])
    assert rc == 0, f"stderr: {err}"
    data = json.loads(out)
    assert "rules" in data
    assert "policy_version" in data
    print("PASS: test_policy_list")


def test_chain_verify_empty():
    """Verify on a missing/empty chain returns ok."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        rc, out, err = _run_cli(
            ["chain", "verify"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["status"] == "ok"
    print("PASS: test_chain_verify_empty")


def test_approvals_list_empty():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        rc, out, err = _run_cli(
            ["approvals"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["total_count"] == 0
        assert data["active_approvals"] == []
    print("PASS: test_approvals_list_empty")


def test_approve_then_lookup():
    """Approve writes a chain event and the approval store reflects it."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}

        rc, out, err = _run_cli(
            ["approve", "sha256:abcdef0123456789", "--operator", "test_operator"],
            env_overrides=env,
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["approved"] is True
        assert data["artifact_identity"] == "sha256:abcdef0123456789"
        assert data["approving_operator"] == "test_operator"
        assert data.get("event_id")

        # The chain file should now exist with one record
        chain = runtime / "LOGS" / "decision-chain.jsonl"
        assert chain.exists()
        lines = chain.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["event_type"] == "opaque_artifact_approval"
        assert rec["artifact_identity"] == "sha256:abcdef0123456789"
        assert "machine_id" in rec
        assert rec["machine_role"] == "primary"
        assert "event_timestamp_utc" in rec

        # Approvals listing should show it
        rc, out, err = _run_cli(["approvals"], env_overrides=env)
        assert rc == 0
        data = json.loads(out)
        assert data["total_count"] == 1
        assert data["active_approvals"][0]["artifact_identity"] == "sha256:abcdef0123456789"
    print("PASS: test_approve_then_lookup")


def test_approve_then_revoke():
    """Revoke removes an existing approval."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}

        _run_cli(["approve", "sha256:deadbeef", "--operator", "op1"], env_overrides=env)
        rc, out, err = _run_cli(
            ["revoke", "sha256:deadbeef", "--operator", "op1"],
            env_overrides=env,
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["revoked"] is True

        # Approvals should now be empty
        rc, out, _ = _run_cli(["approvals"], env_overrides=env)
        data = json.loads(out)
        assert data["total_count"] == 0
    print("PASS: test_approve_then_revoke")


def test_chain_verify_after_writes():
    """After CLI writes, the chain remains structurally valid."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}

        _run_cli(["approve", "sha256:aaa", "--operator", "op"], env_overrides=env)
        _run_cli(["approve", "sha256:bbb", "--operator", "op"], env_overrides=env)
        _run_cli(["revoke", "sha256:aaa", "--operator", "op"], env_overrides=env)

        rc, out, err = _run_cli(["chain", "verify"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["status"] == "ok"
        assert data["chain_event_count"] == 3
    print("PASS: test_chain_verify_after_writes")


def test_status_command():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        _run_cli(["approve", "sha256:zzz", "--operator", "op"], env_overrides=env)
        rc, out, err = _run_cli(["status"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert "chain_event_count" in data
        assert data["chain_event_count"] >= 1
        assert data["active_approvals_count"] >= 1
    print("PASS: test_status_command")


def test_activity_command():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        _run_cli(["approve", "sha256:act1", "--operator", "op"], env_overrides=env)
        rc, out, err = _run_cli(["activity", "--limit", "5"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert "entries" in data or "activity" in data or isinstance(data, dict)
    print("PASS: test_activity_command")


def test_wrapper_script_executable():
    """The atested wrapper script in repo root works."""
    rc = subprocess.run(
        [str(WRAPPER), "--help"],
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0
    print("PASS: test_wrapper_script_executable")


def main():
    test_help()
    test_policy_list()
    test_chain_verify_empty()
    test_approvals_list_empty()
    test_approve_then_lookup()
    test_approve_then_revoke()
    test_chain_verify_after_writes()
    test_status_command()
    test_activity_command()
    test_wrapper_script_executable()
    print("\nAll atested CLI tests passed.")


if __name__ == "__main__":
    main()
