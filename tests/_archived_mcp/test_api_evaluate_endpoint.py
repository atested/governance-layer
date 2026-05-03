#!/usr/bin/env python3
"""Tests for the /api/evaluate HTTP endpoint.

Verifies:
1. ALLOW for valid requests within governed scope
2. DENY for requests outside governed scope
3. 401 for unauthenticated requests
4. 400 for malformed requests
5. Chain record is produced for evaluated actions
"""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "remote_server.py"
AUTH_TOKEN = "govmcp-test-token-evaluate"


def _choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_post(url: str, data: dict, token: str | None = None) -> tuple[int, dict]:
    """Make an HTTP POST request, return (status_code, parsed_json)."""
    body = json.dumps(data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(err_body)
        except json.JSONDecodeError:
            return e.code, {"raw": err_body[:500]}


def _wait_for_server(port: int, proc: subprocess.Popen, max_attempts: int = 50) -> None:
    """Wait for the HTTP server to become available."""
    for _ in range(max_attempts):
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise RuntimeError(f"Server exited early: {err}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Server did not start in time")


async def main() -> None:
    port = _choose_free_port()
    # Use a fresh temp runtime dir to avoid chain integrity issues from other tests.
    tmp_runtime = Path(tempfile.mkdtemp(prefix="govmcp-eval-test-"))
    chain_path = tmp_runtime / "LOGS" / "decision-chain.jsonl"

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(tmp_runtime)
    env["GOVMCP_HOST"] = "127.0.0.1"
    env["GOVMCP_PORT"] = str(port)
    env["GOVMCP_STREAMABLE_HTTP_PATH"] = "/mcp"
    env["GOVMCP_LOG_LEVEL"] = "ERROR"
    env["GOVMCP_REMOTE_AUTH_TOKEN"] = AUTH_TOKEN
    # Use test signing key for chain integrity
    env["GOV_SIGNING_KEY_PATH"] = str(REPO / "system" / "tests" / "fixtures" / "keys" / "ed25519_test_private.pem")
    env["GOV_VERIFY_KEY_PATH"] = str(REPO / "system" / "tests" / "fixtures" / "keys" / "ed25519_test_public.pem")

    # Record chain length before test
    chain_len_before = 0

    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        _wait_for_server(port, proc)
        base = f"http://127.0.0.1:{port}"
        evaluate_url = f"{base}/api/evaluate"
        passed = 0
        total = 0

        # --- Test 1: 401 for unauthenticated request ---
        total += 1
        status, body = _http_post(evaluate_url, {"action": "FS_READ", "target": "."}, token=None)
        assert status == 401, f"T1: expected 401, got {status}: {body}"
        passed += 1
        print(f"  PASS: T1 — unauthenticated request returns 401")

        # --- Test 2: 400 for missing action field ---
        total += 1
        status, body = _http_post(evaluate_url, {"target": "/tmp/foo"}, token=AUTH_TOKEN)
        assert status == 400, f"T2: expected 400, got {status}: {body}"
        assert "action" in body.get("error", ""), f"T2: error should mention 'action': {body}"
        passed += 1
        print(f"  PASS: T2 — missing action field returns 400")

        # --- Test 3: 400 for empty body ---
        total += 1
        # Send empty JSON object
        status, body = _http_post(evaluate_url, {}, token=AUTH_TOKEN)
        assert status == 400, f"T3: expected 400, got {status}: {body}"
        passed += 1
        print(f"  PASS: T3 — empty body returns 400")

        # --- Test 4: ALLOW for valid FS_READ within governed scope ---
        total += 1
        status, body = _http_post(
            evaluate_url,
            {
                "action": "FS_READ",
                "target": str(REPO / "README.md"),
                "evidence": {"goal": "Read README for test"},
            },
            token=AUTH_TOKEN,
        )
        assert status == 200, f"T4: expected 200, got {status}: {body}"
        assert body.get("decision") == "ALLOW", f"T4: expected ALLOW, got {body}"
        assert body.get("record_hash") is not None, f"T4: missing record_hash: {body}"
        passed += 1
        print(f"  PASS: T4 — valid FS_READ returns ALLOW with record_hash")

        # --- Test 5: DENY for path outside governed scope ---
        total += 1
        status, body = _http_post(
            evaluate_url,
            {
                "action": "FS_WRITE",
                "target": "/etc/passwd",
                "evidence": {"goal": "Test denied write"},
            },
            token=AUTH_TOKEN,
        )
        assert status == 200, f"T5: expected 200, got {status}: {body}"
        assert body.get("decision") == "DENY", f"T5: expected DENY, got {body}"
        assert body.get("missing") is not None, f"T5: missing 'missing' field: {body}"
        passed += 1
        print(f"  PASS: T5 — write outside scope returns DENY with missing conditions")

        # --- Test 6: Unknown tool is auto-classified (INV-009) ---
        total += 1
        status, body = _http_post(
            evaluate_url,
            {
                "action": "NONEXISTENT_TOOL",
                "target": "/tmp/foo",
            },
            token=AUTH_TOKEN,
        )
        assert status == 200, f"T6: expected 200, got {status}: {body}"
        # INV-009: unknown tools are auto-classified, not immediately denied.
        # The tool may still be DENY (e.g. path outside scope) but the reason
        # should NOT be "Unknown tool" — it should be a policy reason.
        classification = body.get("classification", {})
        assert classification.get("auto_classified") is True, f"T6: expected auto_classified=True: {body}"
        assert classification.get("original_tool") == "NONEXISTENT_TOOL", f"T6: original_tool mismatch: {body}"
        assert classification.get("classified_as"), f"T6: missing classified_as: {body}"
        passed += 1
        print(f"  PASS: T6 — unknown tool is auto-classified (INV-009)")

        # --- Test 7: Friendly action name resolution ---
        total += 1
        status, body = _http_post(
            evaluate_url,
            {
                "action": "fs_read",
                "target": str(REPO / "README.md"),
                "evidence": {"goal": "Test case-insensitive action name"},
            },
            token=AUTH_TOKEN,
        )
        assert status == 200, f"T7: expected 200, got {status}: {body}"
        assert body.get("decision") == "ALLOW", f"T7: expected ALLOW for lowercase fs_read, got {body}"
        passed += 1
        print(f"  PASS: T7 — lowercase action name resolves correctly")

        # --- Test 8: Chain record produced ---
        total += 1
        chain_len_after = 0
        if chain_path.exists():
            chain_len_after = sum(1 for _ in chain_path.open())
        # Tests 4, 5, 7 should each produce a chain record (T6 is handled before chain)
        new_records = chain_len_after - chain_len_before
        assert new_records >= 2, f"T8: expected >=2 new chain records, got {new_records}"
        passed += 1
        print(f"  PASS: T8 — {new_records} new chain records produced")

        print(f"\n  {passed}/{total} tests passed")
        assert passed == total, f"Some tests failed: {passed}/{total}"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        shutil.rmtree(tmp_runtime, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
