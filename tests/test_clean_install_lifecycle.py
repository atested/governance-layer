from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))

import scripts.atested_cli as atested_cli


def _start_args(**overrides):
    data = {
        "role": "primary",
        "primary_url": None,
        "primary_public_key_pem": None,
        "primary_public_key_pem_file": None,
        "sync_host": "127.0.0.1",
        "sync_port": 8765,
        "sync_interval": 300,
        "dirs": None,
        "user_identity": "clean-install-test",
        "upstream": None,
        "yes_shell_profile": False,
        "no_shell_profile": True,
        "force": False,
        "no_services": True,
        "json": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _run_lifecycle_init(monkeypatch, runtime: Path):
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(
        atested_cli,
        "_set_launchd_env",
        lambda: {"applied": False, "reason": "test_disabled"},
    )
    return atested_cli.cmd_start(_start_args())


def _run_lifecycle_stop():
    return atested_cli.cmd_stop(SimpleNamespace(json=True))


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_listen(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError(f"port {port} did not become ready")


class _MockAnthropicHandler(BaseHTTPRequestHandler):
    response_body = {
        "id": "msg_mock",
        "type": "message",
        "role": "assistant",
        "content": [],
        "stop_reason": "end_turn",
    }
    requests_seen = 0

    def do_POST(self):
        type(self).requests_seen += 1
        length = int(self.headers.get("content-length") or "0")
        if length:
            self.rfile.read(length)
        body = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


@pytest.fixture
def mock_upstream():
    _MockAnthropicHandler.requests_seen = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockAnthropicHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _post(port: int, body: bytes) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(
        "POST",
        "/anthropic/v1/messages",
        body=body,
        headers={"content-type": "application/json", "x-api-key": "test"},
    )
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, payload


def _verify_signed_decision(record: dict, signing_key_path: Path, monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("verify_record_mod", SCRIPTS / "verify-record.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    monkeypatch.setenv("GOV_SIGNING_KEY_PATH", str(signing_key_path))
    rc, lines = verifier.verify_record_dict(record, check_cap_registry_hash=True)
    assert rc == 0, lines
    assert record["signature"]
    assert record["signing_key_id"]


def test_lifecycle_start_bootstraps_runtime_and_is_idempotent(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    assert _run_lifecycle_init(monkeypatch, runtime) == 0

    signing_key = runtime / atested_cli.SIGNING_KEY_NAME
    qa_key = runtime / atested_cli.QA_SIGNING_KEY_NAME
    qa_chain = runtime / "LOGS" / "qa-chain.jsonl"
    identity_path = runtime / "machines" / "identity.json"
    registry_path = runtime / "machines" / "registry.json"

    assert signing_key.exists()
    assert qa_key.exists()
    assert oct(signing_key.stat().st_mode & 0o777) == "0o600"
    assert oct(qa_key.stat().st_mode & 0o777) == "0o600"
    assert oct(qa_chain.stat().st_mode & 0o777) == "0o600"

    key_bytes = signing_key.read_bytes()
    machine_id = json.loads(identity_path.read_text(encoding="utf-8"))["machine_id"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["machines"][0]["machine_id"] == machine_id
    assert registry["machines"][0]["keys"][0]["public_key_pem"]

    qa_records = _records(qa_chain)
    assert len(qa_records) == 1
    snapshot = qa_records[0]
    assert snapshot["event_type"] == "qa_environmental_snapshot"
    assert snapshot["overall"] == "healthy"
    assert snapshot["snapshot_source"] == "lifecycle_install_bootstrap"
    assert snapshot["completed_periodic_assessment"] is False
    assert snapshot["signature"]

    assert _run_lifecycle_init(monkeypatch, runtime) == 0
    assert signing_key.read_bytes() == key_bytes
    assert json.loads(identity_path.read_text(encoding="utf-8"))["machine_id"] == machine_id
    assert len(_records(qa_chain)) == 1


def test_lifecycle_supervisor_propagates_mock_upstream_and_signs_record(
    tmp_path,
    monkeypatch,
    mock_upstream,
):
    runtime = tmp_path / "runtime"
    proxy_port = _free_port()
    dashboard_port = _free_port()
    sync_port = _free_port()
    upstream_url = f"http://127.0.0.1:{mock_upstream.server_port}"
    monkeypatch.setenv("GOV_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("GOV_PROXY_PORT", str(proxy_port))
    monkeypatch.setenv("DASHBOARD_PORT", str(dashboard_port))
    monkeypatch.setattr(
        atested_cli,
        "_set_launchd_env",
        lambda: {"applied": False, "reason": "test_disabled"},
    )
    monkeypatch.setattr(
        atested_cli,
        "_unset_launchd_env",
        lambda: {"applied": False, "reason": "test_disabled"},
    )
    _MockAnthropicHandler.response_body = {
        "id": "msg_lifecycle",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_lifecycle",
                "name": "Read",
                "input": {"file_path": str(REPO / "README.md")},
            }
        ],
        "stop_reason": "tool_use",
    }

    try:
        rc = atested_cli.cmd_start(
            _start_args(no_services=False, upstream=upstream_url, sync_port=sync_port)
        )
        assert rc == 0
        status = atested_cli._service_statuses()
        proxy_argv = status["proxy"]["argv"]
        assert "--upstream" in proxy_argv
        assert upstream_url in proxy_argv
        _wait_for_listen(proxy_port)
    except AssertionError:
        _run_lifecycle_stop()
        raise

    try:
        status_code, _body = _post(
            proxy_port,
            json.dumps({"model": "mock", "max_tokens": 1, "messages": []}).encode("utf-8"),
        )
        assert status_code == 200
        assert _MockAnthropicHandler.requests_seen >= 1
        records = _records(runtime / "LOGS" / "decision-chain.jsonl")
        decision = next(record for record in records if record.get("record_type") == "mediated_decision")
        _verify_signed_decision(decision, runtime / atested_cli.SIGNING_KEY_NAME, monkeypatch)
    finally:
        _run_lifecycle_stop()
