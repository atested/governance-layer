"""Tests for QS-026 — quality service self-provisioning.

Covers:
  1. Auto-keygen: QS binary generates a PKCS#8 PEM key on first run.
  2. Supervisor auto-build behavior (mocked).
  3. Rust-toolchain-missing degraded path (mocked).
  4. Dashboard conformance reader surfaces the degraded marker.
  5. End-to-end fresh-runtime startup produces a healthy QA chain snapshot.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "dashboard"))

import process_supervisor as ps  # noqa: E402
import conformance as cf  # noqa: E402


QS_BINARY = REPO / "quality-service" / "target" / "release" / "quality-service"


# ---------------------------------------------------------------------------
# Auto-keygen — exercise the actual Rust binary
# ---------------------------------------------------------------------------


def _qs_binary_available() -> bool:
    return QS_BINARY.exists() and os.access(QS_BINARY, os.X_OK)


@pytest.mark.skipif(not _qs_binary_available(), reason="QS binary not built")
def test_qa_signing_key_auto_generated_on_first_run(tmp_path):
    """QS binary writes a PKCS#8 PEM key when no key exists at the configured path."""
    runtime = tmp_path / "runtime"
    (runtime / "LOGS").mkdir(parents=True)
    (runtime / "LOGS" / "decision-chain.jsonl").touch()
    (runtime / "supervisor").mkdir(parents=True)

    key_path = runtime / ".atested-qa-signing-key.pem"
    assert not key_path.exists()

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(runtime)
    env["ATESTED_QS_READY_FILE"] = str(runtime / "supervisor" / "quality-service.ready")
    result = subprocess.run(
        [str(QS_BINARY), "--once"],
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, f"qs failed: {result.stderr.decode()}"
    assert key_path.exists(), "QS should auto-generate the signing key"

    pem = key_path.read_text(encoding="utf-8")
    assert pem.startswith("-----BEGIN PRIVATE KEY-----"), "expect PKCS#8 PEM"
    assert pem.rstrip().endswith("-----END PRIVATE KEY-----")

    # 0o600 perms on POSIX
    mode = key_path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600 perms, got {oct(mode)}"


@pytest.mark.skipif(not _qs_binary_available(), reason="QS binary not built")
def test_qa_signing_key_reused_across_restarts(tmp_path):
    """The auto-generated key persists; a second run uses the same key."""
    runtime = tmp_path / "runtime"
    (runtime / "LOGS").mkdir(parents=True)
    (runtime / "LOGS" / "decision-chain.jsonl").touch()
    (runtime / "supervisor").mkdir(parents=True)

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(runtime)
    env["ATESTED_QS_READY_FILE"] = str(runtime / "supervisor" / "quality-service.ready")

    subprocess.run([str(QS_BINARY), "--once"], env=env, timeout=30, check=True)
    key1 = (runtime / ".atested-qa-signing-key.pem").read_bytes()

    subprocess.run([str(QS_BINARY), "--once"], env=env, timeout=30, check=True)
    key2 = (runtime / ".atested-qa-signing-key.pem").read_bytes()

    assert key1 == key2, "key must persist across restarts"


@pytest.mark.skipif(not _qs_binary_available(), reason="QS binary not built")
def test_first_run_produces_healthy_snapshot(tmp_path):
    """Fresh runtime → QS writes a snapshot whose 'overall' is 'healthy'."""
    runtime = tmp_path / "runtime"
    (runtime / "LOGS").mkdir(parents=True)
    (runtime / "LOGS" / "decision-chain.jsonl").touch()
    (runtime / "supervisor").mkdir(parents=True)

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(runtime)
    env["ATESTED_QS_READY_FILE"] = str(runtime / "supervisor" / "quality-service.ready")
    result = subprocess.run([str(QS_BINARY), "--once"], env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()

    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"
    assert qa_chain.exists()
    snapshots = [
        json.loads(line)
        for line in qa_chain.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("event_type") == "qa_environmental_snapshot"
    ]
    assert snapshots, "expect at least one environmental snapshot"
    assert snapshots[0]["sequence"] == 1
    assert snapshots[0]["overall"] == "healthy", f"snapshot reports {snapshots[0]['overall']}"


# ---------------------------------------------------------------------------
# Supervisor auto-build — mocked
# ---------------------------------------------------------------------------


def test_ensure_binary_returns_existing_when_present(tmp_path, monkeypatch):
    """If the binary exists and source files aren't newer, no build is triggered."""
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    fake_bin = tmp_path / "fakebin"
    fake_bin.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)
    monkeypatch.setenv("ATESTED_QUALITY_SERVICE_BIN", str(fake_bin))

    # Custom binary path is trusted as-is; no build attempted.
    binary, err = ps.ensure_quality_service_binary(runtime)
    assert binary == fake_bin
    assert err is None


def test_ensure_binary_custom_path_missing_reports_error(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    missing = tmp_path / "not-there"
    monkeypatch.setenv("ATESTED_QUALITY_SERVICE_BIN", str(missing))

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert binary == missing
    assert err is not None
    assert "not found" in err


def test_ensure_binary_builds_when_default_missing(tmp_path, monkeypatch):
    """If default binary is missing and cargo is available, cargo build runs."""
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    monkeypatch.delenv("ATESTED_QUALITY_SERVICE_BIN", raising=False)

    fake_src = tmp_path / "quality-service"
    (fake_src / "src").mkdir(parents=True)
    (fake_src / "src" / "main.rs").write_text("fn main() {}\n")
    (fake_src / "Cargo.toml").write_text("[package]\nname='q'\nversion='0.1.0'\nedition='2021'\n")
    fake_target = fake_src / "target" / "release"

    monkeypatch.setattr(ps, "quality_service_source_dir", lambda: fake_src)
    monkeypatch.setattr(
        ps,
        "default_quality_service_bin",
        lambda: fake_target / "quality-service",
    )
    monkeypatch.setattr(
        ps,
        "quality_service_bin_path",
        lambda: fake_target / "quality-service",
    )

    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        fake_target.mkdir(parents=True, exist_ok=True)
        (fake_target / "quality-service").write_bytes(b"#!/bin/sh\nexit 0\n")
        (fake_target / "quality-service").chmod(0o755)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(ps.shutil, "which", lambda name: "/usr/bin/cargo" if name == "cargo" else None)
    monkeypatch.setattr(ps.subprocess, "run", fake_run)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is None, err
    assert captured["argv"][:3] == ["/usr/bin/cargo", "build", "--release"]
    assert binary.exists()


def test_ensure_binary_rust_missing_returns_explicit_reason(tmp_path, monkeypatch):
    """Without `cargo` on PATH, the supervisor reports rust_toolchain_missing."""
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    monkeypatch.delenv("ATESTED_QUALITY_SERVICE_BIN", raising=False)

    fake_src = tmp_path / "quality-service"
    (fake_src / "src").mkdir(parents=True)
    (fake_src / "Cargo.toml").write_text("[package]\nname='q'\nversion='0.1.0'\nedition='2021'\n")

    monkeypatch.setattr(ps, "quality_service_source_dir", lambda: fake_src)
    nonexistent = tmp_path / "no-binary"
    monkeypatch.setattr(ps, "default_quality_service_bin", lambda: nonexistent)
    monkeypatch.setattr(ps, "quality_service_bin_path", lambda: nonexistent)
    monkeypatch.setattr(ps.shutil, "which", lambda name: None)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is not None
    assert err.startswith("rust_toolchain_missing")


def test_ensure_binary_writes_log_on_build_failure(tmp_path, monkeypatch):
    """A failed cargo build leaves a usable log file path in the error message."""
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    monkeypatch.delenv("ATESTED_QUALITY_SERVICE_BIN", raising=False)

    fake_src = tmp_path / "quality-service"
    (fake_src / "src").mkdir(parents=True)
    (fake_src / "Cargo.toml").write_text("[package]\nname='q'\nversion='0.1.0'\nedition='2021'\n")
    fake_bin = tmp_path / "no-binary"

    monkeypatch.setattr(ps, "quality_service_source_dir", lambda: fake_src)
    monkeypatch.setattr(ps, "default_quality_service_bin", lambda: fake_bin)
    monkeypatch.setattr(ps, "quality_service_bin_path", lambda: fake_bin)
    monkeypatch.setattr(ps.shutil, "which", lambda name: "/usr/bin/cargo")

    def fail_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 101, b"", b"compile error")

    monkeypatch.setattr(ps.subprocess, "run", fail_run)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is not None
    assert "cargo build" in err
    assert "exit 101" in err


# ---------------------------------------------------------------------------
# Degraded marker — supervisor writes / clears
# ---------------------------------------------------------------------------


def test_degraded_marker_written_then_cleared(tmp_path):
    runtime = tmp_path / "runtime"
    marker = runtime / "supervisor" / "quality-service.degraded.json"

    ps.write_quality_service_degraded_marker(runtime, "rust_toolchain_missing: cargo not found")
    assert marker.exists()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["reason"].startswith("rust_toolchain_missing")
    assert "updated_utc" in data

    ps.write_quality_service_degraded_marker(runtime, None)
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Dashboard surfaces the degraded reason
# ---------------------------------------------------------------------------


def test_conformance_surfaces_rust_toolchain_missing(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor").mkdir(parents=True)
    (runtime / "LOGS").mkdir(parents=True)
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"  # left absent

    # Write the supervisor's degraded marker
    ps.write_quality_service_degraded_marker(
        runtime, "rust_toolchain_missing: cargo not found on PATH"
    )

    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))

    reader = cf.DashboardQAChainReader(qa_chain)
    payload = cf.build_conformance_payload(reader)

    assert payload["state"] == "halted"
    assert "Rust toolchain not found" in payload["detail"]
    assert payload["quality_service_alive"] is False
    assert payload["quality_service_degraded"]["reason"].startswith("rust_toolchain_missing")


def test_conformance_surfaces_build_failure(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor").mkdir(parents=True)
    (runtime / "LOGS").mkdir(parents=True)
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"

    ps.write_quality_service_degraded_marker(
        runtime, "cargo build --release failed (exit 101); see /tmp/log"
    )
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))

    reader = cf.DashboardQAChainReader(qa_chain)
    payload = cf.build_conformance_payload(reader)
    assert payload["state"] == "halted"
    assert "build failed" in payload["detail"].lower()


def test_conformance_no_degraded_marker_uses_standard_halted(tmp_path, monkeypatch):
    """When the marker is absent, halted detail is the standard chain-unavailable message."""
    runtime = tmp_path / "runtime"
    (runtime / "supervisor").mkdir(parents=True)
    (runtime / "LOGS").mkdir(parents=True)
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"  # absent

    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))

    reader = cf.DashboardQAChainReader(qa_chain)
    payload = cf.build_conformance_payload(reader)
    assert payload["state"] == "halted"
    assert "quality_service_degraded" not in payload


# ---------------------------------------------------------------------------
# build_service_specs threads everything together
# ---------------------------------------------------------------------------


def test_build_service_specs_disables_quality_service_when_rust_missing(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor" / "logs").mkdir(parents=True)
    monkeypatch.delenv("ATESTED_QUALITY_SERVICE_BIN", raising=False)

    fake_src = tmp_path / "quality-service"
    (fake_src / "src").mkdir(parents=True)
    (fake_src / "Cargo.toml").write_text("[package]\nname='q'\nversion='0.1.0'\nedition='2021'\n")
    fake_bin = tmp_path / "no-binary"

    monkeypatch.setattr(ps, "quality_service_source_dir", lambda: fake_src)
    monkeypatch.setattr(ps, "default_quality_service_bin", lambda: fake_bin)
    monkeypatch.setattr(ps, "quality_service_bin_path", lambda: fake_bin)
    monkeypatch.setattr(ps.shutil, "which", lambda name: None)

    specs = ps.build_service_specs("primary", "127.0.0.1", 8765, runtime)
    qs_spec = next(s for s in specs if s["name"] == "quality_service")
    assert qs_spec.get("disabled_at_start") is True
    assert "rust_toolchain_missing" in qs_spec["disabled_reason"]

    # Degraded marker should have been written.
    marker = runtime / "supervisor" / "quality-service.degraded.json"
    assert marker.exists()


def test_managed_service_honors_disabled_at_start(tmp_path):
    runtime = tmp_path / "runtime"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    spec = {
        "name": "quality_service",
        "argv": ["/nonexistent"],
        "disabled_at_start": True,
        "disabled_reason": "rust_toolchain_missing: cargo not found",
    }
    svc = ps.ManagedService(spec, runtime, log_dir, {})
    assert svc.disabled is True
    assert svc.disabled_reason.startswith("rust_toolchain_missing")
    # poll() on a disabled, never-started service is a no-op
    svc.poll()
    assert svc.proc is None
