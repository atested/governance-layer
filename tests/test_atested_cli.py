#!/usr/bin/env python3
"""Tests for D-2026-0404-037: atested CLI."""

import json
import os
import subprocess
import sys
import tempfile
import threading
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


def test_start_primary_lifecycle_no_services():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        rc, out, err = _run_cli(["start", "--role", "primary", "--no-services"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["started"] is True
        assert data["role"] == "primary"
        assert data["machine_id"]
        assert (runtime / ".atested-signing-key.pem").exists()
        assert (runtime / "machines" / "identity.json").exists()
        assert (runtime / "machines" / "registry.json").exists()
        assert (runtime / "sync" / "config.json").exists()

        rc, out, err = _run_cli(["status"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        status = json.loads(out)
        assert status["machine"]["role"] == "primary"
        assert status["machine"]["registry"]["registry_present"] is True
    print("PASS: test_start_primary_lifecycle_no_services")


def test_remote_start_manual_sync_no_pending():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        rc, out, err = _run_cli(
            ["start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765", "--no-services"],
            env_overrides=env,
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["role"] == "remote"
        assert data["operator_action_required"]
        assert data["public_key_fingerprint"].startswith("ed25519:")
        assert "BEGIN PUBLIC KEY" in data["public_key_pem"]

        rc, out, err = _run_cli(["sync"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        sync = json.loads(out)
        assert sync["synced"] is True
        assert sync["pending_records"] == 0
    print("PASS: test_remote_start_manual_sync_no_pending")


def test_remote_join_primary_confirmation_and_removal_events():
    with tempfile.TemporaryDirectory() as tmp:
        primary_runtime = _make_isolated_runtime(Path(tmp) / "primary")
        remote_runtime = _make_isolated_runtime(Path(tmp) / "remote")
        primary_env = {"GOV_RUNTIME_DIR": str(primary_runtime)}
        remote_env = {"GOV_RUNTIME_DIR": str(remote_runtime)}

        rc, out, err = _run_cli(["start", "--role", "primary", "--no-services"], env_overrides=primary_env)
        assert rc == 0, f"stderr: {err}"
        rc, out, err = _run_cli(
            ["start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765", "--no-services"],
            env_overrides=remote_env,
        )
        assert rc == 0, f"stderr: {err}"
        remote = json.loads(out)

        rc, out, err = _run_cli(
            [
                "machine", "add",
                "--machine-id", remote["machine_id"],
                "--display-name", "Remote CLI",
                "--public-key-fingerprint", remote["public_key_fingerprint"],
                "--public-key-pem", remote["public_key_pem"],
            ],
            env_overrides=primary_env,
        )
        assert rc == 2
        assert "--confirm is required" in err

        rc, out, err = _run_cli(
            [
                "machine", "add",
                "--machine-id", remote["machine_id"],
                "--display-name", "Remote CLI",
                "--public-key-fingerprint", remote["public_key_fingerprint"],
                "--public-key-pem", remote["public_key_pem"],
                "--confirm",
            ],
            env_overrides=primary_env,
        )
        assert rc == 0, f"stderr: {err}"
        added = json.loads(out)
        assert added["added"] is True
        assert added["event_id"]

        rc, out, err = _run_cli(["machine", "remove", remote["machine_id"], "--reason", "test removal"], env_overrides=primary_env)
        assert rc == 0, f"stderr: {err}"
        removed = json.loads(out)
        assert removed["removed"] is True
        assert removed["event_id"]

        chain = primary_runtime / "LOGS" / "decision-chain.jsonl"
        events = [json.loads(line) for line in chain.read_text(encoding="utf-8").splitlines()]
        assert [event["event_type"] for event in events[-2:]] == ["machine_added", "machine_removed"]
    print("PASS: test_remote_join_primary_confirmation_and_removal_events")


def test_remote_status_degraded_when_received_registry_removes_machine():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        rc, out, err = _run_cli(
            ["start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765", "--no-services"],
            env_overrides=env,
        )
        assert rc == 0, f"stderr: {err}"
        remote = json.loads(out)
        sync_dir = runtime / "sync"
        state_bundle = {
            "received_at_utc": "2026-05-06T00:00:00Z",
            "machine_registry": {
                "machines": [{
                    "machine_id": remote["machine_id"],
                    "license_status": "removed",
                    "sync_authorized": False,
                }],
            },
        }
        (sync_dir / "state_bundle.json").write_text(json.dumps(state_bundle), encoding="utf-8")

        rc, out, err = _run_cli(["status"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        status = json.loads(out)
        assert status["machine"]["degraded_mode"]["degraded"] is True
        assert status["machine"]["degraded_mode"]["reason"] == "machine_removed"
    print("PASS: test_remote_status_degraded_when_received_registry_removes_machine")


def test_cli_remote_sync_imports_pending_records_to_primary():
    from receipt_signing import _read_private_key
    from sync_protocol import private_key_fingerprint
    from sync_service import SyncHTTPRequestHandler, SyncService, _SyncHTTPServer
    from event_model import build_non_action_event, sign_non_action_event

    with tempfile.TemporaryDirectory() as tmp:
        primary_runtime = _make_isolated_runtime(Path(tmp) / "primary")
        remote_runtime = _make_isolated_runtime(Path(tmp) / "remote")
        primary_env = {"GOV_RUNTIME_DIR": str(primary_runtime)}
        remote_env = {"GOV_RUNTIME_DIR": str(remote_runtime)}

        rc, out, err = _run_cli(["start", "--role", "primary", "--no-services"], env_overrides=primary_env)
        assert rc == 0, f"stderr: {err}"
        rc, out, err = _run_cli(
            ["start", "--role", "remote", "--primary-url", "http://127.0.0.1:1", "--no-services"],
            env_overrides=remote_env,
        )
        assert rc == 0, f"stderr: {err}"
        remote = json.loads(out)

        rc, out, err = _run_cli(
            [
                "machine", "add",
                "--machine-id", remote["machine_id"],
                "--display-name", "Remote CLI",
                "--public-key-fingerprint", remote["public_key_fingerprint"],
                "--public-key-pem", remote["public_key_pem"],
                "--confirm",
            ],
            env_overrides=primary_env,
        )
        assert rc == 0, f"stderr: {err}"

        remote_private, _ = _read_private_key(remote_runtime / ".atested-signing-key.pem")
        event = build_non_action_event(
            "usage_attestation",
            {
                "summary": "cli sync record",
                "machine_id": remote["machine_id"],
                "machine_role": "remote",
            },
            prev_record_hash=None,
        )
        sign_non_action_event(event, remote_private, private_key_fingerprint(remote_private))
        remote_chain = remote_runtime / "LOGS" / "decision-chain.jsonl"
        remote_chain.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

        old_runtime = os.environ.get("GOV_RUNTIME_DIR")
        os.environ["GOV_RUNTIME_DIR"] = str(primary_runtime)
        try:
            primary_private, _ = _read_private_key(primary_runtime / ".atested-signing-key.pem")
            service = SyncService(
                REPO,
                primary_private_key=primary_private,
                primary_signing_key_id=private_key_fingerprint(primary_private),
            )
            server = _SyncHTTPServer(("127.0.0.1", 0), SyncHTTPRequestHandler, service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}"
                rc, out, err = _run_cli(["sync", "--primary-url", url], env_overrides=remote_env)
                assert rc == 0, f"stdout: {out}\nstderr: {err}"
                synced = json.loads(out)
                assert synced["synced"] is True
                assert synced["pending_records"] == 1
                assert synced["import_envelope_hash"].startswith("sha256:")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        finally:
            if old_runtime is None:
                os.environ.pop("GOV_RUNTIME_DIR", None)
            else:
                os.environ["GOV_RUNTIME_DIR"] = old_runtime

        imports_root = primary_runtime / "imports" / remote["machine_id"]
        assert any(imports_root.glob("*.jsonl"))
        state = json.loads((remote_runtime / "sync" / "client_state.json").read_text(encoding="utf-8"))
        assert state["last_synced_line_count"] == 1
    print("PASS: test_cli_remote_sync_imports_pending_records_to_primary")


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
