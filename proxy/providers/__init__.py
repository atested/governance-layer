"""
Provider registry for the Atested governance proxy.

Maps provider names to their implementations. The proxy uses URL prefix
routing to select the appropriate provider for each request.
"""

from .base import BaseProvider, BaseStreamingCollector, ToolCall, StreamAction
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider
from .litellm import LiteLLMProvider

PROVIDERS: dict[str, BaseProvider] = {
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "litellm": LiteLLMProvider(),
}

# URL prefix → provider name mapping
PROVIDER_PREFIXES: dict[str, str] = {
    "/anthropic": "anthropic",
    "/openai": "openai",
    "/gemini": "gemini",
    "/litellm": "litellm",
}


def get_provider(name: str) -> BaseProvider:
    """Look up a provider by name. Raises KeyError if not found."""
    return PROVIDERS[name]


def resolve_provider(raw_path: str) -> tuple[BaseProvider, str]:
    """Resolve a provider from a raw URL path.

    Returns (provider, stripped_path) where stripped_path has the provider
    prefix removed.

    Raises ValueError if no provider prefix matches.
    """
    for prefix, provider_name in PROVIDER_PREFIXES.items():
        if raw_path.startswith(prefix):
            path = raw_path[len(prefix):]
            if not path:
                path = "/"
            return PROVIDERS[provider_name], path
    raise ValueError(f"No provider matches path: {raw_path}")
