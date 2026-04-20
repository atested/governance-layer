#!/usr/bin/env python3
"""
test_provider_openai.py — Tests for the OpenAI provider.

Tests cover:
- Tool call extraction from Chat Completions responses
- Denial rewriting (partial and full denial)
- Streaming collector (delta accumulation, finish_reason handling)
"""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROXY_DIR = REPO / "proxy"
SCRIPTS = REPO / "scripts"
MCP_DIR = REPO / "mcp"
for p in (PROXY_DIR, SCRIPTS, MCP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from proxy.providers.openai import OpenAIProvider, OpenAIStreamingCollector
from proxy.providers.base import ToolCall


class TestOpenAIExtraction(unittest.TestCase):
    """Test tool call extraction from OpenAI Chat Completions responses."""

    def setUp(self):
        self.provider = OpenAIProvider()

    def test_extract_single_tool_call(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "Read",
                            "arguments": '{"file_path": "/tmp/test.txt"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[0].args, {"file_path": "/tmp/test.txt"})
        self.assertEqual(calls[0].call_id, "call_abc123")

    def test_extract_multiple_tool_calls(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "Read", "arguments": '{"path": "a.txt"}'},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "Write", "arguments": '{"path": "b.txt", "content": "hi"}'},
                        },
                    ],
                },
                "finish_reason": "tool_calls",
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[1].tool_name, "Write")

    def test_extract_no_tool_calls(self):
        body = {
            "choices": [{
                "message": {"content": "Hello!"},
                "finish_reason": "stop",
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 0)

    def test_extract_malformed_arguments(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_bad",
                        "type": "function",
                        "function": {"name": "Read", "arguments": "not json"},
                    }],
                },
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args, {"_raw": "not json"})


class TestOpenAIDenials(unittest.TestCase):
    """Test denial rewriting for OpenAI responses."""

    def setUp(self):
        self.provider = OpenAIProvider()

    def test_deny_all_tool_calls(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Write", "arguments": '{"path": "/etc/passwd"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        tc = ToolCall(
            tool_name="Write",
            args={"path": "/etc/passwd"},
            call_id="call_1",
            raw_block=body["choices"][0]["message"]["tool_calls"][0],
        )
        result = self.provider.apply_denials(body, [(tc, "outside base dirs", "deny_outside_base")])

        # All denied → tool_calls removed, content added, finish_reason changed
        msg = result["choices"][0]["message"]
        self.assertNotIn("tool_calls", msg)
        self.assertIn("[Governance] Operation denied", msg["content"])
        self.assertEqual(result["choices"][0]["finish_reason"], "stop")

    def test_deny_partial(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "Read", "arguments": '{"path": "ok.txt"}'},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "Write", "arguments": '{"path": "/etc/passwd"}'},
                        },
                    ],
                },
                "finish_reason": "tool_calls",
            }],
        }
        tc2 = ToolCall(
            tool_name="Write",
            args={"path": "/etc/passwd"},
            call_id="call_2",
            raw_block=body["choices"][0]["message"]["tool_calls"][1],
        )
        result = self.provider.apply_denials(body, [(tc2, "outside base dirs", "deny_outside_base")])

        # Only call_2 removed, call_1 remains
        msg = result["choices"][0]["message"]
        self.assertEqual(len(msg["tool_calls"]), 1)
        self.assertEqual(msg["tool_calls"][0]["id"], "call_1")


class TestOpenAIProviderMethods(unittest.TestCase):
    """Test provider interface methods."""

    def setUp(self):
        self.provider = OpenAIProvider()

    def test_is_tool_endpoint(self):
        self.assertTrue(self.provider.is_tool_endpoint("/v1/chat/completions"))
        self.assertTrue(self.provider.is_tool_endpoint("/v1/chat/completions?foo=bar"))
        self.assertFalse(self.provider.is_tool_endpoint("/v1/models"))
        self.assertFalse(self.provider.is_tool_endpoint("/v1/embeddings"))

    def test_is_streaming(self):
        self.assertTrue(self.provider.is_streaming(json.dumps({"stream": True}).encode()))
        self.assertFalse(self.provider.is_streaming(json.dumps({"stream": False}).encode()))
        self.assertFalse(self.provider.is_streaming(json.dumps({}).encode()))

    def test_get_upstream_url(self):
        url = self.provider.get_upstream_url("/v1/chat/completions", {})
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")

        url = self.provider.get_upstream_url("/v1/chat/completions",
                                              {"openai_upstream": "http://localhost:4000"})
        self.assertEqual(url, "http://localhost:4000/v1/chat/completions")

    def test_forward_headers(self):
        headers = {
            "authorization": "Bearer sk-test",
            "content-type": "application/json",
            "host": "should-be-excluded",
            "x-api-key": "should-be-excluded",
        }
        fwd = self.provider.forward_headers(headers)
        self.assertIn("authorization", fwd)
        self.assertIn("content-type", fwd)
        self.assertNotIn("host", fwd)
        self.assertNotIn("x-api-key", fwd)


class TestOpenAIStreamingCollector(unittest.TestCase):
    """Test OpenAI streaming collector."""

    def test_collect_tool_call_from_deltas(self):
        collector = OpenAIStreamingCollector()

        # First delta: tool call start
        action1 = collector.process_event("", {
            "choices": [{
                "delta": {
                    "tool_calls": [{
                        "index": 0,
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": ""},
                    }],
                },
                "finish_reason": None,
            }],
        })
        self.assertEqual(action1.action, "buffer")
        self.assertIsNone(action1.completed_tool_call)

        # Second delta: argument fragment
        action2 = collector.process_event("", {
            "choices": [{
                "delta": {
                    "tool_calls": [{
                        "index": 0,
                        "function": {"arguments": '{"file_'},
                    }],
                },
                "finish_reason": None,
            }],
        })
        self.assertEqual(action2.action, "buffer")

        # Third delta: more arguments
        action3 = collector.process_event("", {
            "choices": [{
                "delta": {
                    "tool_calls": [{
                        "index": 0,
                        "function": {"arguments": 'path": "/tmp/t.txt"}'},
                    }],
                },
                "finish_reason": None,
            }],
        })
        self.assertEqual(action3.action, "buffer")

        # Finish
        action4 = collector.process_event("", {
            "choices": [{
                "delta": {},
                "finish_reason": "tool_calls",
            }],
        })
        self.assertEqual(action4.action, "buffer")
        self.assertIsNotNone(action4.completed_tool_call)
        self.assertEqual(action4.completed_tool_call.tool_name, "Read")
        self.assertEqual(action4.completed_tool_call.args, {"file_path": "/tmp/t.txt"})

    def test_pass_non_tool_events(self):
        collector = OpenAIStreamingCollector()

        action = collector.process_event("", {
            "choices": [{
                "delta": {"content": "Hello"},
                "finish_reason": None,
            }],
        })
        self.assertEqual(action.action, "pass")

    def test_build_denial_events(self):
        collector = OpenAIStreamingCollector()
        tc = ToolCall(tool_name="Write", args={}, call_id="call_1", raw_block={})
        events = collector.build_denial_events(0, tc, "policy denied", "deny_rule")
        self.assertEqual(len(events), 1)
        data = json.loads(events[0].decode().split("data: ")[1].strip())
        self.assertIn("[Governance] Operation denied", data["choices"][0]["delta"]["content"])
        self.assertEqual(data["choices"][0]["finish_reason"], "stop")

    def test_get_all_completed_tool_calls(self):
        collector = OpenAIStreamingCollector()

        # Two tool calls in one response
        collector.process_event("", {
            "choices": [{
                "delta": {
                    "tool_calls": [
                        {"index": 0, "id": "call_1", "type": "function",
                         "function": {"name": "Read", "arguments": ""}},
                        {"index": 1, "id": "call_2", "type": "function",
                         "function": {"name": "Write", "arguments": ""}},
                    ],
                },
                "finish_reason": None,
            }],
        })
        collector.process_event("", {
            "choices": [{
                "delta": {
                    "tool_calls": [
                        {"index": 0, "function": {"arguments": '{"a": 1}'}},
                        {"index": 1, "function": {"arguments": '{"b": 2}'}},
                    ],
                },
                "finish_reason": None,
            }],
        })
        collector.process_event("", {
            "choices": [{
                "delta": {},
                "finish_reason": "tool_calls",
            }],
        })

        all_calls = collector.get_all_completed_tool_calls()
        self.assertEqual(len(all_calls), 2)
        self.assertEqual(all_calls[0].tool_name, "Read")
        self.assertEqual(all_calls[1].tool_name, "Write")


if __name__ == "__main__":
    unittest.main()
