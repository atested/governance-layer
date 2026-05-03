#!/usr/bin/env python3
import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "remote_server.py"


def _choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


AUTH_TOKEN = "govmcp-test-token"


async def _call_remote(url: str, headers: dict[str, str] | None = None) -> dict:
    async with streamablehttp_client(url, headers=headers) as (r, w, _get_session_id):
        async with ClientSession(r, w) as session:
            await session.initialize()
            resp = await session.call_tool(
                "fs_write",
                {
                    "path": "/tmp/govmcp-remote-smoke-deny.txt",
                    "content": "remote-smoke",
                    "overwrite": False,
                    "request_executable": False,
                },
            )
            payload = json.loads(resp.content[0].text)
            return payload


async def main() -> None:
    port = _choose_free_port()
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str((REPO / "gov_runtime").resolve())
    env["GOVMCP_HOST"] = "127.0.0.1"
    env["GOVMCP_PORT"] = str(port)
    env["GOVMCP_STREAMABLE_HTTP_PATH"] = "/mcp"
    env["GOVMCP_LOG_LEVEL"] = "ERROR"
    env["GOVMCP_REMOTE_AUTH_TOKEN"] = AUTH_TOKEN

    cfg = subprocess.run(
        [sys.executable, str(SERVER), "--print-config"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    contract = json.loads(cfg.stdout)
    assert contract["transport"] == "streamable-http", contract
    assert contract["host"] == "127.0.0.1", contract
    assert contract["port"] == port, contract
    assert contract["streamable_http_path"] == "/mcp", contract
    assert contract["auth_mode"] == "shared_bearer_token", contract
    assert contract["auth_required"] == "yes", contract

    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        url = f"http://127.0.0.1:{port}/mcp"
        last_err = None
        for _ in range(50):
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise AssertionError(
                    f"remote server exited early rc={proc.returncode} stdout={out!r} stderr={err!r}"
                )
            try:
                try:
                    await _call_remote(url)
                except Exception:
                    pass
                else:
                    raise AssertionError("unauthenticated remote call unexpectedly succeeded")
                try:
                    await _call_remote(url, headers={"Authorization": "Bearer wrong-token"})
                except Exception:
                    pass
                else:
                    raise AssertionError("invalid bearer token unexpectedly succeeded")

                payload = await _call_remote(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
                assert payload["policy_decision"] == "DENY", payload
                codes = {row.get("code") for row in payload.get("policy_reasons", [])}
                assert "RC-FS-PATH-DISALLOWED" in codes, payload
                print("PASS: remote GovMCP smoke (streamable-http foundation)")
                return
            except Exception as exc:  # pragma: no cover - retry path depends on startup timing
                last_err = exc
                await asyncio.sleep(0.2)
        raise AssertionError(f"remote server never became callable: {last_err!r}")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
