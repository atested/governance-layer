#!/usr/bin/env python3
"""
Test: concurrent governed tool calls do not corrupt the chain.

Spins up a remote GovMCP server (HTTP/bearer), fires N parallel fs_list
calls from separate MCP client sessions, then verifies:
  1. All N calls returned a valid policy decision.
  2. The chain has N new records with correct prev_record_hash linkage.
  3. verify-chain.py passes on the resulting chain.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "remote_server.py"
VERIFY_CHAIN = REPO / "scripts" / "verify-chain.py"
CONCURRENCY = 10

AUTH_TOKEN = "concurrent-test-token"


def _choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _call_fs_list(url: str, path: str) -> dict:
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    async with streamablehttp_client(url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            resp = await session.call_tool("fs_list", {"path": path})
            return json.loads(resp.content[0].text)


async def main() -> None:
    port = _choose_free_port()
    runtime_dir = tempfile.mkdtemp(prefix="govmcp-concurrent-test-")
    chain_path = os.path.join(runtime_dir, "LOGS", "decision-chain.jsonl")
    os.makedirs(os.path.join(runtime_dir, "LOGS"), exist_ok=True)
    os.makedirs(os.path.join(runtime_dir, "tmp"), exist_ok=True)

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = runtime_dir
    env["GOV_CANONICAL_REPO_PATH"] = str(REPO)
    env["GOV_RUNTIME_PATH"] = runtime_dir
    env["GOVMCP_HOST"] = "127.0.0.1"
    env["GOVMCP_PORT"] = str(port)
    env["GOVMCP_STREAMABLE_HTTP_PATH"] = "/mcp"
    env["GOVMCP_LOG_LEVEL"] = "ERROR"
    env["GOVMCP_REMOTE_AUTH_TOKEN"] = AUTH_TOKEN

    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        url = f"http://127.0.0.1:{port}/mcp"

        # Wait for server to start
        for _ in range(50):
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise AssertionError(f"server exited early: {out!r} {err!r}")
            try:
                await _call_fs_list(url, str(REPO))
                break
            except Exception:
                await asyncio.sleep(0.2)
        else:
            raise AssertionError("server never became callable")

        # Count existing chain records (from warmup)
        warmup_count = 0
        if os.path.exists(chain_path):
            with open(chain_path, "r") as f:
                warmup_count = sum(1 for line in f if line.strip())

        # Fire CONCURRENCY parallel calls
        tasks = [_call_fs_list(url, str(REPO)) for _ in range(CONCURRENCY)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 1. All calls should have returned a valid policy decision
        successes = 0
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"  call {i} failed: {r}")
            else:
                assert r.get("policy_decision") in ("ALLOW", "DENY"), f"unexpected: {r}"
                successes += 1
        assert successes == CONCURRENCY, f"only {successes}/{CONCURRENCY} succeeded"
        print(f"  {successes}/{CONCURRENCY} concurrent calls returned valid decisions")

        # 2. Chain has exactly CONCURRENCY new records with correct linkage
        with open(chain_path, "r") as f:
            lines = [l for l in f if l.strip()]
        new_records = lines[warmup_count:]
        assert len(new_records) == CONCURRENCY, (
            f"expected {CONCURRENCY} new chain records, got {len(new_records)}"
        )

        prev_hash = ""
        if warmup_count > 0:
            prev_hash = json.loads(lines[warmup_count - 1])["record_hash"]
        for i, line in enumerate(new_records):
            rec = json.loads(line)
            assert "record_hash" in rec, f"record {i} missing record_hash"
            rec_prev = rec.get("prev_record_hash", "")
            assert rec_prev == prev_hash, (
                f"record {i} prev_record_hash mismatch: got {rec_prev!r}, expected {prev_hash!r}"
            )
            prev_hash = rec["record_hash"]
        print(f"  chain linkage verified for {CONCURRENCY} new records")

        # 3. verify-chain.py passes
        vp = subprocess.run(
            [sys.executable, str(VERIFY_CHAIN), chain_path],
            capture_output=True,
            text=True,
        )
        assert vp.returncode == 0, f"verify-chain failed: {vp.stdout} {vp.stderr}"
        print("  verify-chain.py: PASS")

        print(f"PASS: concurrent chain safety ({CONCURRENCY} parallel writes)")
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
