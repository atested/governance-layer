"""
anthropic.py — Anthropic Messages API provider for the Atested governance proxy.

Handles tool_use extraction, denial rewriting, and streaming collection
for the Anthropic Messages API format.
"""

import json
from typing import Optional

from .base import BaseProvider, BaseStreamingCollector, StreamAction, ToolCall

ANTHROPIC_DEFAULT_UPSTREAM = "https://api.anthropic.com"


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Messages API."""

    name = "anthropic"

    def get_upstream_url(self, path: str, config: dict) -> str:
        base = config.get("anthropic_upstream", ANTHROPIC_DEFAULT_UPSTREAM).rstrip("/")
        return f"{base}{path}"

    def forward_headers(self, request_headers: dict) -> dict:
        forwarded = {}
        for k, v in request_headers.items():
            kl = k.lower() if k != k.lower() else k
            if kl in ("x-api-key", "anthropic-version", "anthropic-beta",
                       "content-type", "authorization", "accept"):
                forwarded[k] = v
        return forwarded

    def is_tool_endpoint(self, path: str) -> bool:
        path_base = path.split("?")[0]
        return path_base.rstrip("/").endswith("/v1/messages")

    def is_streaming(self, body: bytes) -> bool:
        try:
            return json.loads(body).get("stream", False)
        except (json.JSONDecodeError, AttributeError):
            return False

    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        content = response_body.get("content", [])
        results = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                results.append(ToolCall(
                    tool_name=block.get("name", ""),
                    args=block.get("input", {}),
                    call_id=block.get("id", ""),
                    raw_block=block,
                ))
        return results

    def response_format_known(self, response_body: dict) -> bool:
        return "content" in response_body or "error" in response_body

    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        denied_ids = {tc.call_id for tc, _, _ in denials}
        denial_map = {tc.call_id: (tc, reason, rule) for tc, reason, rule in denials}

        new_content = []
        for block in response_body.get("content", []):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("id") in denied_ids
            ):
                tc, reason, rule = denial_map[block["id"]]
                new_content.append({
                    "type": "text",
                    "text": (
                        f"[Governance] Operation denied: {tc.tool_name}\n"
                        f"Reason: {reason}\n"
                        f"Rule: {rule}\n"
                        f"The operation was classified and denied by policy before execution."
                    ),
                })
            else:
                new_content.append(block)

        response_body["content"] = new_content

        # Update stop_reason if no tool_use blocks remain
        remaining = [b for b in new_content
                     if isinstance(b, dict) and b.get("type") == "tool_use"]
        if not remaining and response_body.get("stop_reason") == "tool_use":
            response_body["stop_reason"] = "end_turn"

        return response_body

    def create_streaming_collector(self) -> "AnthropicStreamingCollector":
        return AnthropicStreamingCollector()


class AnthropicStreamingCollector(BaseStreamingCollector):
    """Collects tool_use blocks from Anthropic SSE streams."""

    def __init__(self):
        # Active tool_use blocks being collected, keyed by index
        self._active_blocks: dict[int, dict] = {}
        # JSON fragments for each block index
        self._json_fragments: dict[int, list[str]] = {}
        # Buffered SSE event bytes for each block index
        self._buffered_events: dict[int, list[bytes]] = {}

    def process_event(self, event_type: str, data: dict) -> StreamAction:
        msg_type = data.get("type", "")

        if msg_type == "content_block_start":
            block = data.get("content_block", {})
            if block.get("type") == "tool_use":
                idx = data.get("index", 0)
                self._active_blocks[idx] = {
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": {},
                }
                self._json_fragments[idx] = []
                self._buffered_events[idx] = []
                return StreamAction(action="buffer", index=idx)
            return StreamAction(action="pass")

        if msg_type == "content_block_delta":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                delta = data.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    self._json_fragments.setdefault(idx, []).append(
                        delta.get("partial_json", "")
                    )
                return StreamAction(action="buffer", index=idx)
            return StreamAction(action="pass")

        if msg_type == "content_block_stop":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                block = self._active_blocks.pop(idx)
                fragments = self._json_fragments.pop(idx, [])

                full_json = "".join(fragments)
                if full_json:
                    try:
                        block["input"] = json.loads(full_json)
                    except json.JSONDecodeError:
                        block["input"] = {"_raw": full_json}

                tool_call = ToolCall(
                    tool_name=block["name"],
                    args=block.get("input", {}),
                    call_id=block["id"],
                    raw_block=block,
                )
                return StreamAction(
                    action="buffer",
                    index=idx,
                    completed_tool_call=tool_call,
                )
            return StreamAction(action="pass")

        return StreamAction(action="pass")

    def add_buffered_event(self, index: int, event_bytes: bytes) -> None:
        """Store a raw SSE event for later flush on ALLOW."""
        self._buffered_events.setdefault(index, []).append(event_bytes)

    def build_denial_events(
        self,
        index: int,
        tool_call: ToolCall,
        reason: str,
        matched_rule: str,
    ) -> list[bytes]:
        denial_text = (
            f"[Governance] Operation denied: {tool_call.tool_name}\n"
            f"Reason: {reason}\n"
            f"Rule: {matched_rule}\n"
            f"The operation was classified and denied by policy before execution."
        )
        events = []

        start_data = json.dumps({
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "text", "text": ""},
        })
        events.append(f"event: content_block_start\ndata: {start_data}\n\n".encode())

        delta_data = json.dumps({
            "type": "content_block_delta",
            "index": index,
            "delta": {"type": "text_delta", "text": denial_text},
        })
        events.append(f"event: content_block_delta\ndata: {delta_data}\n\n".encode())

        stop_data = json.dumps({
            "type": "content_block_stop",
            "index": index,
        })
        events.append(f"event: content_block_stop\ndata: {stop_data}\n\n".encode())

        return events

    def get_buffered_events(self, index: int) -> list[bytes]:
        return self._buffered_events.pop(index, [])
