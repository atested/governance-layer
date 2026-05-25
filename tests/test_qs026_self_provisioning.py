"""Tests for quality service prebuilt-binary provisioning.

Covers:
  1. Auto-keygen: QS binary generates a PKCS#8 PEM key on first run.
  2. Supervisor prebuilt binary manifest verification (mocked).
  3. Missing/hash-mismatch degraded paths (mocked).
  4. Dashboard conformance reader surfaces the degraded marker.
  5. End-to-end fresh-runtime startup produces a healthy QA chain snapshot.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import hashlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "dashboard"))

import process_supervisor as ps  # noqa: E402
import conformance as cf  # noqa: E402


QS_TARGET = ps.quality_service_target_triple()
QS_BINARY = (
    REPO / "quality-service" / "prebuilt" / f"quality-service-{QS_TARGET}"
    if QS_TARGET
    else REPO / "quality-service" / "prebuilt" / "quality-service-unsupported"
)


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
    """Fresh runtime → QS writes a healthy snapshot with binary provenance."""
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
    manifest = json.loads(
        (REPO / "quality-service" / "prebuilt" / "quality-service-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert snapshots[0]["binary_sha256"] == manifest["binaries"][QS_TARGET]["sha256"]


# ---------------------------------------------------------------------------
# Supervisor prebuilt binary verification — mocked
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(repo: Path, target: str, rel_path: str, sha256: str | None) -> Path:
    manifest = repo / "quality-service" / "prebuilt" / "quality-service-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "binaries": {
                    target: {
                        "status": "available",
                        "target_triple": target,
                        "path": rel_path,
                        "sha256": sha256,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_ensure_binary_returns_existing_when_manifest_matches(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    repo = tmp_path / "repo"
    target = "aarch64-apple-darwin"
    rel_path = f"quality-service/prebuilt/quality-service-{target}"
    fake_bin = repo / rel_path
    fake_bin.parent.mkdir(parents=True)
    fake_bin.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)
    _write_manifest(repo, target, rel_path, _sha256(fake_bin))
    monkeypatch.setattr(ps, "REPO", repo)
    monkeypatch.setattr(ps, "quality_service_target_triple", lambda: target)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert binary == fake_bin
    assert err is None


def test_ensure_binary_missing_reports_error(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    repo = tmp_path / "repo"
    target = "aarch64-apple-darwin"
    rel_path = f"quality-service/prebuilt/quality-service-{target}"
    _write_manifest(repo, target, rel_path, "sha256:" + "0" * 64)
    monkeypatch.setattr(ps, "REPO", repo)
    monkeypatch.setattr(ps, "quality_service_target_triple", lambda: target)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is not None
    assert binary == repo / rel_path
    assert err.startswith("quality_service_binary_missing")


def test_ensure_binary_hash_mismatch_reports_error(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    repo = tmp_path / "repo"
    target = "aarch64-apple-darwin"
    rel_path = f"quality-service/prebuilt/quality-service-{target}"
    fake_bin = repo / rel_path
    fake_bin.parent.mkdir(parents=True)
    fake_bin.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)
    _write_manifest(repo, target, rel_path, "sha256:" + "0" * 64)
    monkeypatch.setattr(ps, "REPO", repo)
    monkeypatch.setattr(ps, "quality_service_target_triple", lambda: target)

    binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is not None
    assert binary == fake_bin
    assert err.startswith("quality_service_binary_hash_mismatch")


def test_ensure_binary_unsupported_platform_reports_error(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(ps, "quality_service_target_triple", lambda: None)

    _binary, err = ps.ensure_quality_service_binary(runtime)
    assert err is not None
    assert err.startswith("quality_service_platform_unsupported")


# ---------------------------------------------------------------------------
# Degraded marker — supervisor writes / clears
# ---------------------------------------------------------------------------


def test_degraded_marker_written_then_cleared(tmp_path):
    runtime = tmp_path / "runtime"
    marker = runtime / "supervisor" / "quality-service.degraded.json"

    ps.write_quality_service_degraded_marker(runtime, "quality_service_binary_missing: not found")
    assert marker.exists()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["reason"].startswith("quality_service_binary_missing")
    assert "updated_utc" in data

    ps.write_quality_service_degraded_marker(runtime, None)
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Dashboard surfaces the degraded reason
# ---------------------------------------------------------------------------


def test_conformance_surfaces_missing_prebuilt_binary(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor").mkdir(parents=True)
    (runtime / "LOGS").mkdir(parents=True)
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"  # left absent

    # Write the supervisor's degraded marker
    ps.write_quality_service_degraded_marker(
        runtime, "quality_service_binary_missing: expected prebuilt binary"
    )

    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))

    reader = cf.DashboardQAChainReader(qa_chain)
    payload = cf.build_conformance_payload(reader)

    assert payload["state"] == "halted"
    assert "binary is missing" in payload["detail"]
    assert payload["quality_service_alive"] is False
    assert payload["quality_service_degraded"]["reason"].startswith("quality_service_binary_missing")


def test_conformance_surfaces_hash_mismatch(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    (runtime / "supervisor").mkdir(parents=True)
    (runtime / "LOGS").mkdir(parents=True)
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"

    ps.write_quality_service_degraded_marker(
        runtime, "quality_service_binary_hash_mismatch: expected sha256:a actual sha256:b"
    )
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))

    reader = cf.DashboardQAChainReader(qa_chain)
    payload = cf.build_conformance_payload(reader)
    assert payload["state"] == "halted"
    assert "manifest verification" in payload["detail"].lower()


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


def test_build_service_specs_disables_quality_service_when_binary_missing(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(
        ps,
        "ensure_quality_service_binary",
        lambda runtime: (tmp_path / "no-binary", "quality_service_binary_missing: expected prebuilt binary"),
    )

    specs = ps.build_service_specs("primary", "127.0.0.1", 8765, runtime)
    qs_spec = next(s for s in specs if s["name"] == "quality_service")
    assert qs_spec.get("disabled_at_start") is True
    assert "quality_service_binary_missing" in qs_spec["disabled_reason"]

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
        "disabled_reason": "quality_service_binary_missing: not found",
    }
    svc = ps.ManagedService(spec, runtime, log_dir, {})
    assert svc.disabled is True
    assert svc.disabled_reason.startswith("quality_service_binary_missing")
    # poll() on a disabled, never-started service is a no-op
    svc.poll()
    assert svc.proc is None
