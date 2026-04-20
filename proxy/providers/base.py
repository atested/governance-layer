"""
base.py — Abstract provider interface for the Atested governance proxy.

Defines the contract that all provider implementations must satisfy.
The proxy dispatches to providers based on URL prefix routing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    """A single tool call extracted from a provider response."""
    tool_name: str
    args: dict
    call_id: str        # Provider-native ID (e.g., Anthropic tool_use id, OpenAI call id)
    raw_block: dict     # Original block for reconstruction


@dataclass
class StreamAction:
    """Result of processing a single SSE event in a streaming collector."""
    action: str         # "pass", "buffer", or "replace"
    index: int = 0
    completed_tool_call: Optional[ToolCall] = None


class BaseProvider(ABC):
    """Abstract provider interface.

    Each provider knows how to:
    - Route requests to the correct upstream
    - Extract auth headers for forwarding
    - Detect tool-bearing endpoints
    - Parse tool calls from responses (streaming and non-streaming)
    - Apply denials by rewriting response bodies
    """

    name: str = ""

    @abstractmethod
    def get_upstream_url(self, path: str, config: dict) -> str:
        """Build the full upstream URL for a given request path."""

    @abstractmethod
    def forward_headers(self, request_headers: dict) -> dict:
        """Select and transform headers to forward upstream."""

    @abstractmethod
    def is_tool_endpoint(self, path: str) -> bool:
        """Return True if this path can contain tool calls in the response."""

    @abstractmethod
    def is_streaming(self, body: bytes) -> bool:
        """Return True if the request body indicates a streaming request."""

    @abstractmethod
    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        """Extract tool calls from a non-streaming response body."""

    @abstractmethod
    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        """Apply denial rewrites to a response body.

        Args:
            response_body: Parsed JSON response.
            denials: List of (tool_call, reason, matched_rule) tuples.

        Returns:
            Modified response body with denied tool calls replaced.
        """

    @abstractmethod
    def create_streaming_collector(self) -> "BaseStreamingCollector":
        """Create a new streaming collector for this provider's SSE format."""


class BaseStreamingCollector(ABC):
    """Collects tool calls from a provider's streaming SSE format.

    The collector buffers tool_use events, reassembles complete tool calls,
    and returns StreamAction results. Governance mediation is performed by
    GovernanceProxy, not by the collector — the collector only signals when
    a tool call is complete.
    """

    @abstractmethod
    def process_event(self, event_type: str, data: dict) -> StreamAction:
        """Process a single parsed SSE event.

        Returns a StreamAction indicating what the proxy should do:
        - "pass": forward the event as-is
        - "buffer": hold the event (part of a tool call being assembled)
        - "replace": not used directly by collector (proxy handles denial)

        When a tool call is fully assembled, the StreamAction should include
        the completed ToolCall in completed_tool_call.
        """

    @abstractmethod
    def build_denial_events(
        self,
        index: int,
        tool_call: ToolCall,
        reason: str,
        matched_rule: str,
    ) -> list[bytes]:
        """Build SSE event bytes that replace a denied tool call."""

    @abstractmethod
    def get_buffered_events(self, index: int) -> list[bytes]:
        """Return buffered SSE events for a given block index (for flush on ALLOW)."""
