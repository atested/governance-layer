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


# ---------------------------------------------------------------------------
# QS-061: per-provider timeout end-to-end
# ---------------------------------------------------------------------------


class TestOllamaTimeoutWiring(unittest.TestCase):
    """Verify Ollama traffic goes through with the configured timeout AND
    that the proxy records a governed chain entry tagged provider=ollama.

    Spinning up a live Ollama is out of scope for this sandboxed test, so we
    swap httpx.AsyncClient for a fake that returns a non-streaming Ollama
    response. The fake records the timeout it was constructed with so the
    test can assert provider_timeout_seconds() actually reached the client.
    """

    def test_non_streaming_uses_per_provider_timeout_and_records_provider(self):
        import asyncio
        import importlib
        import json as _json

        proxy_server = importlib.import_module("proxy.server")

        captured = {"timeout": None, "url": None, "chain_records": []}

        class _FakeResponse:
            status_code = 200
            content = _json.dumps({
                "model": "llama3:8b",
                "message": {"role": "assistant", "content": "hello"},
                "done": True,
            }).encode()
            headers = {"content-type": "application/json"}

            async def aread(self):
                return self.content

        class _FakeClient:
            def __init__(self, timeout=None, **kw):
                captured["timeout"] = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def request(self, method, url, headers=None, content=None):
                captured["url"] = url
                return _FakeResponse()

        class _FakeChainRecorder:
            def append_atomic(self, record):
                captured["chain_records"].append(record)

        # Build the GovernanceProxy with a fake recorder + an Ollama upstream.
        proxy = proxy_server.GovernanceProxy(
            upstream_base="https://api.anthropic.com",
            policy={"rules": [], "default_decision": "ALLOW", "default_reason": "ok"},
            chain_recorder=_FakeChainRecorder(),
            session_id="test-session",
            user_identity="test-operator",
            provider_config={
                "ollama_upstream": "http://localhost:11434",
                # Custom timeout — must flow through to the http client.
                "ollama_timeout_seconds": 420.0,
            },
        )

        from proxy.providers.ollama import OllamaProvider
        provider = OllamaProvider()

        async def _drive():
            # Patch httpx.AsyncClient inside proxy.server for the duration.
            original = proxy_server.httpx.AsyncClient
            proxy_server.httpx.AsyncClient = _FakeClient
            try:
                status, headers, body = await proxy._handle_non_streaming_provider(
                    url="http://localhost:11434/api/chat",
                    method="POST",
                    headers={"content-type": "application/json"},
                    body=b'{"model":"llama3:8b","messages":[{"role":"user","content":"hi"}]}',
                    is_tool_ep=True,
                    provider=provider,
                )
            finally:
                proxy_server.httpx.AsyncClient = original
            return status, body

        status, body = asyncio.run(_drive())

        # The upstream call must go to the Ollama URL with the per-provider
        # timeout (300s default, 420s here).
        self.assertEqual(captured["url"], "http://localhost:11434/api/chat")
        self.assertEqual(captured["timeout"], 420.0)
        # The proxy must record at least one governed entry tagged ollama.
        providers = {r.get("provider") for r in captured["chain_records"]}
        self.assertIn("ollama", providers,
                      f"expected provider=ollama in chain records, got providers={providers}")
        # And the response must come back to the caller unchanged because the
        # mock response has no tool calls — Ollama answers the user directly.
        self.assertEqual(status, 200)
        parsed = _json.loads(body)
        self.assertEqual(parsed["message"]["content"], "hello")

    def test_default_ollama_timeout_when_unset(self):
        """If no override is provided in provider_config, fall back to 300s."""
        from proxy.server import (
            provider_timeout_seconds,
            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            provider_timeout_seconds("ollama", {}),
            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        )
        self.assertEqual(DEFAULT_OLLAMA_TIMEOUT_SECONDS, 300.0)


if __name__ == "__main__":
    unittest.main()
