#!/usr/bin/env python3
"""
test_provider_routing.py — Routing integration tests for multi-provider support.

Tests cover:
- Provider prefix routing (resolve_provider)
- Provider registry (get_provider, PROVIDERS)
- LiteLLM inherits OpenAI behavior
- Provider config plumbing
- mediate_decision provider_name field
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

from proxy.providers import (
    resolve_provider,
    get_provider,
    PROVIDERS,
    PROVIDER_PREFIXES,
)
from proxy.providers.base import ToolCall
from proxy.providers.anthropic import AnthropicProvider
from proxy.providers.openai import OpenAIProvider
from proxy.providers.gemini import GeminiProvider
from proxy.providers.litellm import LiteLLMProvider
from proxy.server import mediate_decision
from policy_eval_v2 import load_policy_rules


class TestProviderRegistry(unittest.TestCase):
    """Test the provider registry."""

    def test_all_providers_registered(self):
        self.assertIn("anthropic", PROVIDERS)
        self.assertIn("openai", PROVIDERS)
        self.assertIn("gemini", PROVIDERS)
        self.assertIn("litellm", PROVIDERS)

    def test_get_provider(self):
        self.assertIsInstance(get_provider("anthropic"), AnthropicProvider)
        self.assertIsInstance(get_provider("openai"), OpenAIProvider)
        self.assertIsInstance(get_provider("gemini"), GeminiProvider)
        self.assertIsInstance(get_provider("litellm"), LiteLLMProvider)

    def test_get_provider_unknown(self):
        with self.assertRaises(KeyError):
            get_provider("unknown")

    def test_provider_prefixes(self):
        self.assertEqual(PROVIDER_PREFIXES["/anthropic"], "anthropic")
        self.assertEqual(PROVIDER_PREFIXES["/openai"], "openai")
        self.assertEqual(PROVIDER_PREFIXES["/gemini"], "gemini")
        self.assertEqual(PROVIDER_PREFIXES["/litellm"], "litellm")


class TestResolveProvider(unittest.TestCase):
    """Test URL prefix routing."""

    def test_anthropic_prefix(self):
        provider, path = resolve_provider("/anthropic/v1/messages")
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(path, "/v1/messages")

    def test_openai_prefix(self):
        provider, path = resolve_provider("/openai/v1/chat/completions")
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(path, "/v1/chat/completions")

    def test_gemini_prefix(self):
        provider, path = resolve_provider("/gemini/v1beta/models/gemini-pro:generateContent")
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(path, "/v1beta/models/gemini-pro:generateContent")

    def test_litellm_prefix(self):
        provider, path = resolve_provider("/litellm/v1/chat/completions")
        self.assertIsInstance(provider, LiteLLMProvider)
        self.assertEqual(path, "/v1/chat/completions")

    def test_no_match_raises(self):
        with self.assertRaises(ValueError):
            resolve_provider("/unknown/v1/foo")

    def test_prefix_only(self):
        provider, path = resolve_provider("/openai")
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(path, "/")

    def test_with_query_params(self):
        provider, path = resolve_provider("/anthropic/v1/messages?beta=true")
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(path, "/v1/messages?beta=true")


class TestLiteLLMProvider(unittest.TestCase):
    """Test LiteLLM provider specifics."""

    def setUp(self):
        self.provider = LiteLLMProvider()

    def test_inherits_openai_extraction(self):
        body = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Read", "arguments": '{"path": "test.txt"}'},
                    }],
                },
            }],
        }
        calls = self.provider.extract_tool_calls(body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].tool_name, "Read")

    def test_upstream_requires_config(self):
        with self.assertRaises(ValueError) as ctx:
            self.provider.get_upstream_url("/v1/chat/completions", {})
        self.assertIn("not configured", str(ctx.exception))

    def test_upstream_with_config(self):
        url = self.provider.get_upstream_url(
            "/v1/chat/completions",
            {"litellm_upstream": "http://localhost:4000"},
        )
        self.assertEqual(url, "http://localhost:4000/v1/chat/completions")

    def test_name(self):
        self.assertEqual(self.provider.name, "litellm")

    def test_is_tool_endpoint(self):
        self.assertTrue(self.provider.is_tool_endpoint("/v1/chat/completions"))


class TestMediateDecisionProviderField(unittest.TestCase):
    """Test that mediate_decision includes provider field."""

    def test_provider_name_in_record(self):
        policy = dict(load_policy_rules())
        policy["base_dirs"] = [str(REPO)]

        record = mediate_decision(
            "Read",
            {"file_path": str(REPO / "README.md")},
            policy=policy,
            provider_name="openai",
        )
        self.assertEqual(record.get("provider"), "openai")

    def test_provider_name_defaults_when_empty(self):
        policy = dict(load_policy_rules())
        policy["base_dirs"] = [str(REPO)]

        record = mediate_decision(
            "Read",
            {"file_path": str(REPO / "README.md")},
            policy=policy,
            provider_name="",
        )
        self.assertEqual(record.get("provider"), "unknown")

    def test_anthropic_provider_name(self):
        policy = dict(load_policy_rules())
        policy["base_dirs"] = [str(REPO)]

        record = mediate_decision(
            "Read",
            {"file_path": str(REPO / "README.md")},
            policy=policy,
            provider_name="anthropic",
        )
        self.assertEqual(record.get("provider"), "anthropic")


class TestProviderEndpointDetection(unittest.TestCase):
    """Test that each provider correctly detects its tool endpoints."""

    def test_anthropic_messages(self):
        p = AnthropicProvider()
        self.assertTrue(p.is_tool_endpoint("/v1/messages"))
        self.assertTrue(p.is_tool_endpoint("/v1/messages?beta=true"))
        self.assertFalse(p.is_tool_endpoint("/v1/models"))

    def test_openai_chat_completions(self):
        p = OpenAIProvider()
        self.assertTrue(p.is_tool_endpoint("/v1/chat/completions"))
        self.assertTrue(p.is_tool_endpoint("/v1/responses"))
        self.assertFalse(p.is_tool_endpoint("/v1/models"))
        self.assertFalse(p.is_tool_endpoint("/v1/completions"))

    def test_gemini_generate_content(self):
        p = GeminiProvider()
        self.assertTrue(p.is_tool_endpoint("/v1beta/models/gemini-pro:generateContent"))
        self.assertTrue(p.is_tool_endpoint("/v1beta/models/gemini-pro:streamGenerateContent"))
        self.assertFalse(p.is_tool_endpoint("/v1/models"))


class TestProviderUpstreamConfig(unittest.TestCase):
    """Test upstream URL configuration for each provider."""

    def test_anthropic_default(self):
        p = AnthropicProvider()
        url = p.get_upstream_url("/v1/messages", {})
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")

    def test_anthropic_custom(self):
        p = AnthropicProvider()
        url = p.get_upstream_url("/v1/messages",
                                  {"anthropic_upstream": "http://localhost:9000"})
        self.assertEqual(url, "http://localhost:9000/v1/messages")

    def test_openai_default(self):
        p = OpenAIProvider()
        url = p.get_upstream_url("/v1/chat/completions", {})
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")

    def test_gemini_default(self):
        p = GeminiProvider()
        url = p.get_upstream_url("/v1beta/models/gemini-pro:generateContent", {})
        self.assertEqual(url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent")


if __name__ == "__main__":
    unittest.main()
