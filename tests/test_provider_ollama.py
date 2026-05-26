#!/usr/bin/env python3
"""
test_provider_ollama.py — Tests for the Ollama provider (QS-059).

The OllamaProvider mediates a local Ollama server (default
http://localhost:11434) across two surfaces:

  * /v1/chat/completions — OpenAI-compatible, fully inherits the OpenAI
    extractor/denial/streaming logic.
  * /api/chat — Ollama-native, uses a dedicated extractor and denial
    rewriter that handles object-shaped ``arguments`` and the missing
    top-level tool-call ``id`` field.

These tests cover both surfaces, the upstream URL contract, the header
filter (Ollama doesn't speak OpenAI-organization headers), tool-endpoint
detection, and the apply_denials behaviour for partial and full denials.
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

from proxy.providers.ollama import OllamaProvider, OLLAMA_DEFAULT_UPSTREAM
from proxy.providers.openai import OpenAIStreamingCollector
from proxy.providers.base import ToolCall


class TestOllamaUpstream(unittest.TestCase):
    """Upstream URL construction."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_default_upstream_is_localhost_11434(self):
        url = self.provider.get_upstream_url("/v1/chat/completions", {})
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")

    def test_default_upstream_constant_matches(self):
        # The default constant is the contract surface for downstream
        # callers — keep it pinned to the loopback Ollama port.
        self.assertEqual(OLLAMA_DEFAULT_UPSTREAM, "http://localhost:11434")

    def test_native_api_chat_path_routes(self):
        url = self.provider.get_upstream_url("/api/chat", {})
        self.assertEqual(url, "http://localhost:11434/api/chat")

    def test_override_upstream(self):
        url = self.provider.get_upstream_url(
            "/api/chat",
            {"ollama_upstream": "http://ollama.internal:11434"},
        )
        self.assertEqual(url, "http://ollama.internal:11434/api/chat")

    def test_override_strips_trailing_slash(self):
        url = self.provider.get_upstream_url(
            "/v1/chat/completions",
            {"ollama_upstream": "http://localhost:11434/"},
        )
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")


class TestOllamaHeaders(unittest.TestCase):
    """Header forwarding — Ollama doesn't need OpenAI-organization headers."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_forwards_content_type_and_accept(self):
        fwd = self.provider.forward_headers({
            "content-type": "application/json",
            "accept": "application/json",
        })
        self.assertEqual(fwd.get("content-type"), "application/json")
        self.assertEqual(fwd.get("accept"), "application/json")

    def test_forwards_authorization(self):
        # Authorisation is forwarded so an operator can put a reverse proxy
        # with auth in front of Ollama. Ollama itself ignores it.
        fwd = self.provider.forward_headers({"authorization": "Bearer abc"})
        self.assertEqual(fwd.get("authorization"), "Bearer abc")

    def test_drops_openai_specific_headers(self):
        fwd = self.provider.forward_headers({
            "content-type": "application/json",
            "openai-organization": "org_1",
            "openai-project": "proj_1",
            "openai-beta": "tools=v1",
        })
        self.assertEqual(fwd, {"content-type": "application/json"})


class TestOllamaToolEndpoint(unittest.TestCase):
    """Tool-endpoint detection covers both Ollama chat surfaces."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_openai_compatible_path(self):
        self.assertTrue(self.provider.is_tool_endpoint("/v1/chat/completions"))

    def test_native_api_chat_path(self):
        self.assertTrue(self.provider.is_tool_endpoint("/api/chat"))

    def test_with_query_string(self):
        self.assertTrue(self.provider.is_tool_endpoint("/api/chat?foo=bar"))

    def test_with_trailing_slash(self):
        self.assertTrue(self.provider.is_tool_endpoint("/v1/chat/completions/"))

    def test_non_tool_paths(self):
        self.assertFalse(self.provider.is_tool_endpoint("/api/tags"))
        self.assertFalse(self.provider.is_tool_endpoint("/api/generate"))
        self.assertFalse(self.provider.is_tool_endpoint("/v1/models"))


class TestOllamaStreamingFlag(unittest.TestCase):
    """The ``stream`` body flag is detected via the inherited OpenAI logic."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_stream_true(self):
        self.assertTrue(self.provider.is_streaming(b'{"stream": true}'))

    def test_stream_false(self):
        self.assertFalse(self.provider.is_streaming(b'{"stream": false}'))

    def test_stream_absent(self):
        self.assertFalse(self.provider.is_streaming(b'{"model": "qwen2.5"}'))

    def test_malformed_body(self):
        self.assertFalse(self.provider.is_streaming(b"not json"))


class TestOllamaNativeExtraction(unittest.TestCase):
    """Extract tool calls from Ollama's native /api/chat response shape."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_extract_single_native_tool_call(self):
        body = {
            "model": "qwen2.5:7b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {
                        "name": "Read",
                        "arguments": {"file_path": "/tmp/test.txt"},
                    }},
                ],
            },
            "done": True,
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[0].args, {"file_path": "/tmp/test.txt"})
        self.assertEqual(calls[0].call_id, "ollama-tc-0")
        self.assertEqual(calls[0].response_format, "ollama_native")

    def test_extract_multiple_native_tool_calls(self):
        body = {
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "Read", "arguments": {"path": "a"}}},
                    {"function": {"name": "Write",
                                  "arguments": {"path": "b", "content": "x"}}},
                ],
            },
            "done": True,
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[1].tool_name, "Write")
        # Synthesized IDs are unique within a response.
        self.assertNotEqual(calls[0].call_id, calls[1].call_id)

    def test_extract_no_tool_calls(self):
        body = {
            "message": {"role": "assistant", "content": "Hello there."},
            "done": True,
        }
        self.assertEqual(self.provider.extract_tool_calls(body), [])

    def test_extract_handles_stringified_arguments(self):
        # Forward-compat: tolerate JSON-encoded string arguments even though
        # the documented native shape uses an object.
        body = {
            "message": {
                "tool_calls": [
                    {"function": {
                        "name": "Read",
                        "arguments": '{"file_path": "/tmp/x"}',
                    }},
                ],
            },
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args, {"file_path": "/tmp/x"})

    def test_extract_handles_malformed_string_arguments(self):
        body = {
            "message": {
                "tool_calls": [
                    {"function": {"name": "Read", "arguments": "not json"}},
                ],
            },
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args, {"_raw": "not json"})


class TestOllamaOpenAICompatExtraction(unittest.TestCase):
    """The OpenAI-compatible /v1/chat/completions path inherits the parent."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_extract_via_openai_compatible_shape(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "Read",
                            "arguments": '{"file_path": "/tmp/x"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool_name, "Read")
        self.assertEqual(calls[0].call_id, "call_xyz")
        # OpenAI-shape path stamps "chat_completions" response_format.
        self.assertEqual(calls[0].response_format, "chat_completions")


class TestOllamaResponseFormatKnown(unittest.TestCase):
    """response_format_known recognises both Ollama shapes plus errors."""

    def setUp(self):
        self.provider = OllamaProvider()

    def test_openai_compat_shape_known(self):
        self.assertTrue(self.provider.response_format_known({"choices": []}))

    def test_native_shape_known(self):
        self.assertTrue(self.provider.response_format_known({"message": {}}))

    def test_error_shape_known(self):
        self.assertTrue(self.provider.response_format_known({"error": "x"}))

    def test_unknown_shape_rejected(self):
        self.assertFalse(self.provider.response_format_known({"foo": "bar"}))


class TestOllamaNativeDenials(unittest.TestCase):
    """apply_denials on the native /api/chat shape."""

    def setUp(self):
        self.provider = OllamaProvider()

    def _body_with_two_calls(self):
        return {
            "model": "qwen2.5:7b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "Read", "arguments": {"path": "a"}}},
                    {"function": {"name": "Delete", "arguments": {"path": "b"}}},
                ],
            },
            "done": True,
        }

    def test_partial_denial_keeps_allowed_call(self):
        body = self._body_with_two_calls()
        deny_tc = ToolCall(
            tool_name="Delete",
            args={"path": "b"},
            call_id="ollama-tc-1",
            raw_block={},
            response_format="ollama_native",
        )
        out = self.provider.apply_denials(body, [(deny_tc, "outside scope", "rule-x")])
        remaining = out["message"]["tool_calls"]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["function"]["name"], "Read")
        # Partial denial does NOT flip done_reason — the model still has work.
        self.assertNotIn("done_reason", out)

    def test_full_denial_drops_tool_calls_and_writes_denial_text(self):
        body = self._body_with_two_calls()
        tcs = [
            ToolCall(tool_name="Read", args={"path": "a"},
                     call_id="ollama-tc-0", raw_block={},
                     response_format="ollama_native"),
            ToolCall(tool_name="Delete", args={"path": "b"},
                     call_id="ollama-tc-1", raw_block={},
                     response_format="ollama_native"),
        ]
        denials = [
            (tcs[0], "outside scope", "rule-a"),
            (tcs[1], "destructive", "rule-b"),
        ]
        out = self.provider.apply_denials(body, denials)
        self.assertNotIn("tool_calls", out["message"])
        self.assertIn("[Governance] Operation denied: Read", out["message"]["content"])
        self.assertIn("[Governance] Operation denied: Delete", out["message"]["content"])
        self.assertEqual(out.get("done_reason"), "stop")

    def test_openai_compat_denials_route_to_parent(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read",
                                     "arguments": '{"path": "a"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        tc = ToolCall(
            tool_name="Read",
            args={"path": "a"},
            call_id="call_1",
            raw_block={},
            response_format="chat_completions",
        )
        out = self.provider.apply_denials(body, [(tc, "denied", "rule")])
        # All calls denied → parent strips tool_calls and writes denial
        # text into content with finish_reason flipped to "stop".
        msg = out["choices"][0]["message"]
        self.assertNotIn("tool_calls", msg)
        self.assertIn("[Governance] Operation denied: Read", msg["content"])
        self.assertEqual(out["choices"][0]["finish_reason"], "stop")


class TestOllamaStreamingCollector(unittest.TestCase):
    """The collector reuses OpenAI's SSE collector for /v1/chat/completions."""

    def test_collector_is_openai_compatible(self):
        provider = OllamaProvider()
        collector = provider.create_streaming_collector()
        # /v1/chat/completions is OpenAI-compatible — we deliberately reuse
        # the OpenAI SSE collector here. /api/chat NDJSON streaming is a
        # documented limitation (QS-059).
        self.assertIsInstance(collector, OpenAIStreamingCollector)


if __name__ == "__main__":
    unittest.main()
