"""
litellm.py — LiteLLM provider for the Atested governance proxy.

LiteLLM uses the OpenAI Chat Completions format but routes to a
configurable upstream (typically a local LiteLLM proxy instance).
"""

from .openai import OpenAIProvider


class LiteLLMProvider(OpenAIProvider):
    """Provider for LiteLLM — OpenAI format with configurable upstream."""

    name = "litellm"

    def get_upstream_url(self, path: str, config: dict) -> str:
        base = config.get("litellm_upstream", "")
        if not base:
            raise ValueError(
                "LiteLLM upstream not configured. "
                "Set --litellm-upstream or LITELLM_UPSTREAM environment variable."
            )
        return f"{base.rstrip('/')}{path}"
