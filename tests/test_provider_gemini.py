#!/usr/bin/env python3
"""
test_provider_gemini.py — Tests for the Gemini provider.

Tests cover:
- Function call extraction from generateContent responses
- Denial rewriting (functionCall → text part)
- Streaming collector (complete function calls in single chunks)
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

from proxy.providers.gemini import GeminiProvider, GeminiStreamingCollector
from proxy.providers.base import ToolCall


class TestGeminiExtraction(unittest.TestCase):
    """Test function call extraction from Gemini responses."""

    def setUp(self):
        self.provider = GeminiProvider()

    def test_extract_single_function_call(self):
        body = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "Read",
                            "args": {"file_path": "/tmp/test.txt"},
                        },
                    }],
                    "role": "model",
                },
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[0].args, {"file_path": "/tmp/test.txt"})
        self.assertEqual(calls[0].call_id, "gemini-fc-0")

    def test_extract_multiple_function_calls(self):
        body = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"functionCall": {"name": "Read", "args": {"path": "a.txt"}}},
                        {"text": "some text between"},
                        {"functionCall": {"name": "Write", "args": {"path": "b.txt"}}},
                    ],
                    "role": "model",
                },
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[0].call_id, "gemini-fc-0")
        self.assertEqual(calls[1].tool_name, "Write")
        self.assertEqual(calls[1].call_id, "gemini-fc-2")  # index 2 since text part is at 1

    def test_extract_no_function_calls(self):
        body = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello!"}],
                    "role": "model",
                },
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 0)

    def test_extract_empty_candidates(self):
        body = {"candidates": []}
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 0)


class TestGeminiDenials(unittest.TestCase):
    """Test denial rewriting for Gemini responses."""

    def setUp(self):
        self.provider = GeminiProvider()

    def test_deny_function_call(self):
        body = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {"name": "Write", "args": {"path": "/etc/passwd"}},
                    }],
                    "role": "model",
                },
            }],
        }
        tc = ToolCall(
            tool_name="Write",
            args={"path": "/etc/passwd"},
            call_id="gemini-fc-0",
            raw_block=body["candidates"][0]["content"]["parts"][0],
        )
        result = self.provider.apply_denials(body, [(tc, "outside base dirs", "deny_outside_base")])

        parts = result["candidates"][0]["content"]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertNotIn("functionCall", parts[0])
        self.assertIn("[Governance] Operation denied", parts[0]["text"])
        self.assertIn("Write", parts[0]["text"])

    def test_deny_partial_preserves_text(self):
        body = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "Let me help you with that."},
                        {"functionCall": {"name": "Write", "args": {"path": "/etc/passwd"}}},
                    ],
                    "role": "model",
                },
            }],
        }
        tc = ToolCall(
            tool_name="Write",
            args={"path": "/etc/passwd"},
            call_id="gemini-fc-1",
            raw_block=body["candidates"][0]["content"]["parts"][1],
        )
        result = self.provider.apply_denials(body, [(tc, "policy denied", "deny_rule")])

        parts = result["candidates"][0]["content"]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["text"], "Let me help you with that.")
        self.assertIn("[Governance]", parts[1]["text"])


class TestGeminiProviderMethods(unittest.TestCase):
    """Test provider interface methods."""

    def setUp(self):
        self.provider = GeminiProvider()

    def test_is_tool_endpoint(self):
        self.assertTrue(self.provider.is_tool_endpoint(
            "/v1beta/models/gemini-pro:generateContent"))
        self.assertTrue(self.provider.is_tool_endpoint(
            "/v1beta/models/gemini-pro:streamGenerateContent"))
        self.assertFalse(self.provider.is_tool_endpoint("/v1/models"))

    def test_is_streaming_path(self):
        self.assertTrue(self.provider.is_streaming_path(
            "/v1beta/models/gemini-pro:streamGenerateContent"))
        self.assertFalse(self.provider.is_streaming_path(
            "/v1beta/models/gemini-pro:generateContent"))

    def test_is_streaming_body(self):
        # Gemini doesn't use body for streaming detection
        self.assertFalse(self.provider.is_streaming(b'{}'))

    def test_get_upstream_url(self):
        url = self.provider.get_upstream_url(
            "/v1beta/models/gemini-pro:generateContent", {})
        self.assertEqual(url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent")

    def test_forward_headers(self):
        headers = {
            "x-goog-api-key": "AIza...",
            "content-type": "application/json",
            "host": "should-be-excluded",
        }
        fwd = self.provider.forward_headers(headers)
        self.assertIn("x-goog-api-key", fwd)
        self.assertIn("content-type", fwd)
        self.assertNotIn("host", fwd)


class TestGeminiStreamingCollector(unittest.TestCase):
    """Test Gemini streaming collector."""

    def test_collect_complete_function_call(self):
        collector = GeminiStreamingCollector()

        action = collector.process_event("", {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "Read",
                            "args": {"file_path": "/tmp/test.txt"},
                        },
                    }],
                    "role": "model",
                },
            }],
        })
        self.assertEqual(action.action, "buffer")
        self.assertIsNotNone(action.completed_tool_call)
        self.assertEqual(action.completed_tool_call.tool_name, "Read")

    def test_pass_text_events(self):
        collector = GeminiStreamingCollector()

        action = collector.process_event("", {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello!"}],
                    "role": "model",
                },
            }],
        })
        self.assertEqual(action.action, "pass")

    def test_build_denial_events(self):
        collector = GeminiStreamingCollector()
        tc = ToolCall(tool_name="Write", args={}, call_id="gemini-fc-0", raw_block={})
        events = collector.build_denial_events(0, tc, "policy denied", "deny_rule")
        self.assertEqual(len(events), 1)
        data = json.loads(events[0].decode().split("data: ")[1].strip())
        self.assertIn("[Governance] Operation denied",
                      data["candidates"][0]["content"]["parts"][0]["text"])


if __name__ == "__main__":
    unittest.main()
