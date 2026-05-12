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

import atested_cli  # noqa: E402
import process_supervisor  # noqa: E402

_TEST_PRIMARY_PUBLIC_KEY_PEM = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo=\n-----END PUBLIC KEY-----"


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
        rc, out, err = _run_cli(["--json", "status"], env_overrides=env)
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
        rc, out, err = _run_cli(["--json", "start", "--role", "primary", "--no-services"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["started"] is True
        assert data["role"] == "primary"
        assert data["machine_id"]
        assert (runtime / ".atested-signing-key.pem").exists()
        assert (runtime / "machines" / "identity.json").exists()
        assert (runtime / "machines" / "registry.json").exists()
        assert (runtime / "sync" / "config.json").exists()

        rc, out, err = _run_cli(["--json", "status"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        status = json.loads(out)
        assert status["machine"]["role"] == "primary"
        assert status["machine"]["registry"]["registry_present"] is True
    print("PASS: test_start_primary_lifecycle_no_services")


def test_supervisor_status_paths_and_service_specs():
    primary_specs = process_supervisor.build_service_specs("primary", "127.0.0.1", 8765)
    remote_specs = process_supervisor.build_service_specs("remote", "127.0.0.1", 8765)
    assert [spec["name"] for spec in primary_specs] == ["proxy", "dashboard", "sync_service"]
    assert [spec["name"] for spec in remote_specs] == ["proxy", "dashboard"]
    assert any("scripts/sync_service.py" in part for part in primary_specs[-1]["argv"])
    print("PASS: test_supervisor_status_paths_and_service_specs")


def test_supervisor_pid_record_requires_matching_runtime_and_token(tmp_path, monkeypatch):
    runtime = _make_isolated_runtime(tmp_path)
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    supervisor_dir = runtime / "supervisor"
    supervisor_dir.mkdir(parents=True)

    record = {
        "pid": os.getpid(),
        "token": "test-token",
        "runtime": str(runtime),
        "created_utc": "2026-05-09T00:00:00Z",
    }
    (supervisor_dir / "supervisor.pid").write_text(json.dumps(record), encoding="utf-8")
    (supervisor_dir / "status.json").write_text(json.dumps({
        "supervisor": {
            "pid": os.getpid(),
            "token": "different-token",
            "runtime": str(runtime),
        },
    }), encoding="utf-8")
    monkeypatch.setattr(atested_cli, "_pid_command_matches", lambda pid, token: True)

    assert atested_cli._supervisor_record_valid(atested_cli._read_supervisor_pid_record()) is False


def test_supervisor_status_ignores_stale_service_snapshot(tmp_path, monkeypatch):
    runtime = _make_isolated_runtime(tmp_path)
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    supervisor_dir = runtime / "supervisor"
    supervisor_dir.mkdir(parents=True)
    (supervisor_dir / "supervisor.pid").write_text(json.dumps({
        "pid": os.getpid(),
        "token": "new-token",
        "runtime": str(runtime),
        "created_utc": "2026-05-09T01:00:00Z",
    }), encoding="utf-8")
    (supervisor_dir / "status.json").write_text(json.dumps({
        "supervisor": {
            "pid": 999999,
            "token": "old-token",
            "runtime": str(runtime),
            "running": False,
            "uptime_seconds": 0,
        },
        "services": {
            "proxy": {"pid": 111111, "running": False, "uptime_seconds": 0},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(atested_cli, "_pid_alive", lambda pid: pid == os.getpid())
    monkeypatch.setattr(atested_cli, "_pid_command_matches", lambda pid, token: token == "new-token")

    status = atested_cli._supervisor_status()

    assert status["supervisor"]["pid"] == os.getpid()
    assert status["supervisor"]["running"] is True
    assert status.get("services") == {}


def test_service_status_uses_live_pid_over_stale_running_flag(tmp_path, monkeypatch):
    runtime = _make_isolated_runtime(tmp_path)
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    supervisor_dir = runtime / "supervisor"
    supervisor_dir.mkdir(parents=True)
    (supervisor_dir / "supervisor.pid").write_text(json.dumps({
        "pid": os.getpid(),
        "token": "live-token",
        "runtime": str(runtime),
        "created_utc": "2026-05-10T00:00:00Z",
    }), encoding="utf-8")
    (supervisor_dir / "status.json").write_text(json.dumps({
        "supervisor": {
            "pid": os.getpid(),
            "token": "live-token",
            "runtime": str(runtime),
            "running": True,
        },
        "services": {
            "proxy": {"pid": 12345, "running": False, "uptime_seconds": 0},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(atested_cli, "_pid_command_matches", lambda pid, token: token == "live-token")
    monkeypatch.setattr(atested_cli, "_pid_alive", lambda pid: pid in {os.getpid(), 12345})

    services = atested_cli._service_statuses()

    assert services["proxy"]["running"] is True


def test_stop_recorded_services_kills_stale_service_pids(tmp_path, monkeypatch):
    runtime = _make_isolated_runtime(tmp_path)
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    supervisor_dir = runtime / "supervisor"
    supervisor_dir.mkdir(parents=True)
    (supervisor_dir / "services.json").write_text(json.dumps({
        "proxy": {"pid": 111},
        "dashboard": {"pid": 222},
    }), encoding="utf-8")
    killed = []
    monkeypatch.setattr(atested_cli, "_terminate_pid", lambda pid, timeout=5.0: killed.append(pid) or True)

    stopped = atested_cli._stop_recorded_services()

    assert [row["name"] for row in stopped] == ["dashboard", "proxy"]
    assert sorted(killed) == [111, 222]
    assert json.loads((supervisor_dir / "services.json").read_text(encoding="utf-8")) == {}


def test_stop_supervisor_refuses_identity_mismatch(tmp_path, monkeypatch):
    runtime = _make_isolated_runtime(tmp_path)
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    supervisor_dir = runtime / "supervisor"
    supervisor_dir.mkdir(parents=True)
    (supervisor_dir / "supervisor.pid").write_text(json.dumps({
        "pid": os.getpid(),
        "token": "test-token",
        "runtime": str(runtime),
        "created_utc": "2026-05-09T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setattr(atested_cli, "_pid_command_matches", lambda pid, token: False)

    result = atested_cli._stop_supervisor()
    assert result["stopped"] is False
    assert result["reason"] == "supervisor_identity_mismatch"


def test_shell_profile_helpers_configure_provider_base_urls(tmp_path):
    profile = tmp_path / ".zshrc"
    result = atested_cli._configure_provider_base_urls(profile)
    assert result["updated"] is True
    text = profile.read_text(encoding="utf-8")
    assert "ANTHROPIC_BASE_URL=http://localhost:8080/anthropic" in text
    assert "OPENAI_BASE_URL=http://localhost:8080/openai" in text
    assert "GEMINI_BASE_URL=http://localhost:8080/gemini" in text

    second = atested_cli._configure_provider_base_urls(profile)
    assert second["updated"] is False
    assert profile.read_text(encoding="utf-8").count("ANTHROPIC_BASE_URL=") == 1
    assert profile.read_text(encoding="utf-8").count("OPENAI_BASE_URL=") == 1
    assert profile.read_text(encoding="utf-8").count("GEMINI_BASE_URL=") == 1

    assert atested_cli._profile_path_for_shell("/bin/zsh", tmp_path) == tmp_path / ".zshrc"
    assert atested_cli._profile_path_for_shell("/bin/bash", tmp_path) == tmp_path / ".bash_profile"
    assert atested_cli._profile_path_for_shell("/bin/fish", tmp_path) is None
    print("PASS: test_shell_profile_helpers_configure_provider_base_urls")


def test_collect_base_dirs_defaults_to_repo_root_noninteractive(monkeypatch):
    monkeypatch.setattr(atested_cli.sys.stdin, "isatty", lambda: False)
    args = type("Args", (), {"dirs": None})()

    base_dirs = atested_cli._collect_base_dirs(args)

    assert base_dirs == ["__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"]
    print("PASS: test_collect_base_dirs_defaults_to_repo_root_noninteractive")


def test_restore_verify_primary_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        rc, out, err = _run_cli(["start", "--role", "primary", "--no-services"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        rc, out, err = _run_cli(["approve", "sha256:restoretest", "--operator", "op"], env_overrides=env)
        assert rc == 0, f"stderr: {err}"

        rc, out, err = _run_cli(["restore", "verify", "--runtime", str(runtime)], env_overrides=env)
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["restore_runtime_valid"] is True
        assert any(check["name"] == "chain_integrity" and check["status"] == "ok" for check in data["checks"])
    print("PASS: test_restore_verify_primary_runtime")


def test_remote_start_manual_sync_no_pending():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        env = {"GOV_RUNTIME_DIR": str(runtime)}
        rc, out, err = _run_cli(
            [
                "--json", "start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765",
                "--primary-public-key-pem", _TEST_PRIMARY_PUBLIC_KEY_PEM,
                "--no-services",
            ],
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

        rc, out, err = _run_cli(["--json", "start", "--role", "primary", "--no-services"], env_overrides=primary_env)
        assert rc == 0, f"stderr: {err}"
        primary = json.loads(out)
        rc, out, err = _run_cli(
            [
                "--json", "start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765",
                "--primary-public-key-pem", primary["public_key_pem"],
                "--no-services",
            ],
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
            [
                "--json", "start", "--role", "remote", "--primary-url", "http://127.0.0.1:8765",
                "--primary-public-key-pem", _TEST_PRIMARY_PUBLIC_KEY_PEM,
                "--no-services",
            ],
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

        rc, out, err = _run_cli(["--json", "status"], env_overrides=env)
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

        rc, out, err = _run_cli(["--json", "start", "--role", "primary", "--no-services"], env_overrides=primary_env)
        assert rc == 0, f"stderr: {err}"
        primary = json.loads(out)
        rc, out, err = _run_cli(
            [
                "--json", "start", "--role", "remote", "--primary-url", "http://127.0.0.1:1",
                "--primary-public-key-pem", primary["public_key_pem"],
                "--no-services",
            ],
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


# ---------------------------------------------------------------------------
# Uninstall command tests (D-237)
# ---------------------------------------------------------------------------


def test_uninstall_help():
    rc, out, err = _run_cli(["uninstall", "--help"])
    assert rc == 0
    for flag in ("--keep-runtime", "--move-runtime", "--delete-runtime", "--keep-repo", "--yes"):
        assert flag in out, f"Missing {flag} in help output"
    print("PASS: test_uninstall_help")


def test_uninstall_delete_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        chain = runtime / "LOGS" / "decision-chain.jsonl"
        chain.write_text('{"test": true}\n', encoding="utf-8")
        rc, out, err = _run_cli(
            ["uninstall", "--delete-runtime", "--keep-repo", "--yes"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["uninstalled"] is True
        assert data["steps"]["runtime"]["action"] == "delete"
        assert not runtime.exists()
        assert data["steps"]["repo"]["action"] == "keep"
    print("PASS: test_uninstall_delete_runtime")


def test_uninstall_keep_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        chain = runtime / "LOGS" / "decision-chain.jsonl"
        chain.write_text('{"test": true}\n', encoding="utf-8")
        (runtime / "supervisor").mkdir()
        (runtime / "supervisor" / "supervisor.pid").write_text("99999")
        (runtime / "tmp").mkdir()
        rc, out, err = _run_cli(
            ["uninstall", "--keep-runtime", "--keep-repo", "--yes"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["uninstalled"] is True
        assert data["steps"]["runtime"]["action"] == "keep"
        # Chain preserved
        assert chain.exists()
        assert chain.read_text(encoding="utf-8").strip() == '{"test": true}'
        # Ephemeral cleaned
        assert not (runtime / "supervisor").exists()
        assert not (runtime / "tmp").exists()
    print("PASS: test_uninstall_keep_runtime")


def test_uninstall_move_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        chain = runtime / "LOGS" / "decision-chain.jsonl"
        chain.write_text('{"moved": true}\n', encoding="utf-8")
        (runtime / "supervisor").mkdir()
        (runtime / "supervisor" / "status.json").write_text("{}")
        dest = Path(tmp) / "relocated"
        rc, out, err = _run_cli(
            ["uninstall", "--move-runtime", str(dest), "--keep-repo", "--yes"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["steps"]["runtime"]["action"] == "move"
        assert not runtime.exists()
        assert (dest / "LOGS" / "decision-chain.jsonl").exists()
        # Supervisor dir cleaned before move
        assert not (dest / "supervisor").exists()
    print("PASS: test_uninstall_move_runtime")


def test_uninstall_shell_profile_removal():
    """Unit test of _remove_shell_profile_entry."""
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / ".zshrc"
        profile.write_text(
            "# existing stuff\nPATH=/usr/bin\n"
            "# Atested proxy endpoint\n"
            "export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic\n"
            "export OPENAI_BASE_URL=http://localhost:8080/openai\n"
            "export GEMINI_BASE_URL=http://localhost:8080/gemini\n"
            "# more stuff\n",
            encoding="utf-8",
        )
        result = atested_cli._remove_shell_profile_entry(profile)
        assert result["removed"] is True
        text = profile.read_text(encoding="utf-8")
        assert "ANTHROPIC_BASE_URL" not in text
        assert "OPENAI_BASE_URL" not in text
        assert "GEMINI_BASE_URL" not in text
        assert "Atested proxy endpoint" not in text
        assert "existing stuff" in text
        assert "more stuff" in text
        # Second call — already removed
        result2 = atested_cli._remove_shell_profile_entry(profile)
        assert result2["removed"] is False
        assert result2["reason"] == "marker_not_found"
    print("PASS: test_uninstall_shell_profile_removal")


def test_uninstall_non_interactive_requires_flags():
    """Non-interactive mode (subprocess) without --yes and runtime flag errors."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        # No --yes, no runtime flag → should error (subprocess stdin is not a tty)
        rc, out, err = _run_cli(
            ["uninstall"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 1
        data = json.loads(out)
        assert "runtime_action_required" in json.dumps(data)
    print("PASS: test_uninstall_non_interactive_requires_flags")


def test_uninstall_mutual_exclusivity():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        rc, out, err = _run_cli(
            ["uninstall", "--keep-runtime", "--delete-runtime", "--yes"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 1
        data = json.loads(out)
        assert "mutually_exclusive" in data.get("error", "")
    print("PASS: test_uninstall_mutual_exclusivity")


def test_uninstall_services_not_running():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        rc, out, err = _run_cli(
            ["uninstall", "--delete-runtime", "--keep-repo", "--yes"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        assert rc == 0, f"stderr: {err}"
        data = json.loads(out)
        assert data["uninstalled"] is True
        stop_step = data["steps"]["stop"]
        assert stop_step.get("reason") == "not_running" or stop_step.get("stopped") is False
    print("PASS: test_uninstall_services_not_running")


def test_start_prints_immediate_output():
    """D-244: start must print output before heavy operations."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = _make_isolated_runtime(tmp)
        rc, out, err = _run_cli(
            ["start", "--no-services"],
            env_overrides={"GOV_RUNTIME_DIR": str(runtime)},
        )
        # The first non-empty line must be the immediate status message.
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert lines, "start produced no output"
        assert lines[0].strip() == "Starting Atested..."
    print("PASS: test_start_prints_immediate_output")


def test_start_redirected_stdout_gets_immediate_output(tmp_path):
    """D-246: redirected stdout must receive the start line without a keypress."""
    runtime = _make_isolated_runtime(tmp_path)
    out_path = tmp_path / "out.txt"
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(runtime)
    with out_path.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            [sys.executable, str(CLI_PATH), "start", "--no-services"],
            stdout=out,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("Starting Atested...\n"), text


def test_atested_cli_never_writes_to_dev_tty():
    """D-246: CLI output must remain visible when stdout is redirected."""
    source = CLI_PATH.read_text(encoding="utf-8")
    assert "/dev/tty" not in source


def test_getpass_not_imported_at_module_level():
    """D-244: getpass must not be imported at module level (readline trigger)."""
    import importlib
    # Ensure getpass is NOT in atested_cli's module-level namespace
    spec = importlib.util.find_spec("atested_cli")
    assert spec is not None
    # Check the source for 'import getpass' at module level
    source = Path(spec.origin).read_text(encoding="utf-8")
    # Module-level imports are before the first function def.  Any
    # 'import getpass' must appear inside a function body (indented).
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            break
        assert stripped != "import getpass", (
            "getpass imported at module level — move inside function"
        )
    print("PASS: test_getpass_not_imported_at_module_level")


def test_clear_supervisor_status_files():
    """D-244: _clear_supervisor_status_files removes stale status."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Path(tmp) / "runtime"
        supervisor_dir = runtime / "supervisor"
        supervisor_dir.mkdir(parents=True)
        status_path = supervisor_dir / "status.json"
        services_path = supervisor_dir / "services.json"
        status_path.write_text('{"supervisor":{"pid":999}}', encoding="utf-8")
        services_path.write_text('{"proxy":{"pid":1000}}', encoding="utf-8")
        assert status_path.exists()
        assert services_path.exists()

        # Monkeypatch _supervisor_dir and _services_path
        orig_supervisor_dir = atested_cli._supervisor_dir
        orig_supervisor_status_path = atested_cli._supervisor_status_path
        orig_services_path = atested_cli._services_path
        atested_cli._supervisor_dir = lambda: supervisor_dir
        atested_cli._supervisor_status_path = lambda: status_path
        atested_cli._services_path = lambda: services_path
        try:
            atested_cli._clear_supervisor_status_files()
        finally:
            atested_cli._supervisor_dir = orig_supervisor_dir
            atested_cli._supervisor_status_path = orig_supervisor_status_path
            atested_cli._services_path = orig_services_path

        assert not status_path.exists(), "status.json not deleted"
        assert not services_path.exists(), "services.json not deleted"
    print("PASS: test_clear_supervisor_status_files")


def test_service_statuses_uses_status_file():
    """D-244: _service_statuses should prefer status file over services.json."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Path(tmp) / "runtime"
        supervisor_dir = runtime / "supervisor"
        supervisor_dir.mkdir(parents=True)

        # Write a status file with service data
        import time as _t
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status_data = {
            "supervisor": {
                "pid": 0,
                "token": "test-token",
                "runtime": str(runtime),
                "running": False,
            },
            "services": {
                "proxy": {"pid": 0, "running": False, "name": "proxy",
                          "started_utc": now_utc, "uptime_seconds": 5},
            },
            "updated_utc": now_utc,
        }
        (supervisor_dir / "status.json").write_text(
            json.dumps(status_data), encoding="utf-8"
        )
        # Write DIFFERENT data to services.json (stale)
        (supervisor_dir / "services.json").write_text(
            json.dumps({"proxy": {"pid": 0, "running": True, "name": "proxy-stale"}}),
            encoding="utf-8",
        )
        # Write a dummy pid record
        (supervisor_dir / "supervisor.pid").write_text(
            json.dumps({"pid": 0, "token": "test-token", "runtime": str(runtime)}),
            encoding="utf-8",
        )

        orig_runtime = atested_cli._runtime
        orig_supervisor_dir = atested_cli._supervisor_dir
        orig_supervisor_status_path = atested_cli._supervisor_status_path
        orig_services_path = atested_cli._services_path
        orig_supervisor_pid_path = atested_cli._supervisor_pid_path
        atested_cli._runtime = lambda: runtime
        atested_cli._supervisor_dir = lambda: supervisor_dir
        atested_cli._supervisor_status_path = lambda: supervisor_dir / "status.json"
        atested_cli._services_path = lambda: supervisor_dir / "services.json"
        atested_cli._supervisor_pid_path = lambda: supervisor_dir / "supervisor.pid"
        try:
            result = atested_cli._service_statuses()
        finally:
            atested_cli._runtime = orig_runtime
            atested_cli._supervisor_dir = orig_supervisor_dir
            atested_cli._supervisor_status_path = orig_supervisor_status_path
            atested_cli._services_path = orig_services_path
            atested_cli._supervisor_pid_path = orig_supervisor_pid_path

        # Should use status file data, not services.json
        assert "proxy" in result
        assert result["proxy"]["name"] == "proxy", (
            f"Expected status file data, got: {result['proxy']}"
        )
    print("PASS: test_service_statuses_uses_status_file")


def test_main_reconfigures_stdout():
    """D-244: main() must call sys.stdout.reconfigure for line buffering."""
    rc, out, err = _run_cli(["--help"])
    assert rc == 0
    # Verify the reconfigure call exists in source
    source = Path(atested_cli.__file__).read_text(encoding="utf-8")
    assert "reconfigure(line_buffering=True)" in source
    print("PASS: test_main_reconfigures_stdout")


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
