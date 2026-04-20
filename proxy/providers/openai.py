"""
openai.py — OpenAI Chat Completions API provider for the Atested governance proxy.

Handles tool_calls extraction, denial rewriting, and streaming collection
for the OpenAI Chat Completions format.
"""

import json
from typing import Optional

from .base import BaseProvider, BaseStreamingCollector, StreamAction, ToolCall

OPENAI_DEFAULT_UPSTREAM = "https://api.openai.com"


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI Chat Completions API."""

    name = "openai"

    def get_upstream_url(self, path: str, config: dict) -> str:
        base = config.get("openai_upstream", OPENAI_DEFAULT_UPSTREAM).rstrip("/")
        return f"{base}{path}"

    def forward_headers(self, request_headers: dict) -> dict:
        forwarded = {}
        for k, v in request_headers.items():
            kl = k.lower() if k != k.lower() else k
            if kl in ("authorization", "content-type", "accept",
                       "openai-organization", "openai-project"):
                forwarded[k] = v
        return forwarded

    def is_tool_endpoint(self, path: str) -> bool:
        path_base = path.split("?")[0]
        return path_base.rstrip("/").endswith("/v1/chat/completions")

    def is_streaming(self, body: bytes) -> bool:
        try:
            return json.loads(body).get("stream", False)
        except (json.JSONDecodeError, AttributeError):
            return False

    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        results = []
        choices = response_body.get("choices", [])
        if not choices:
            return results
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        for tc in tool_calls:
            if tc.get("type") != "function":
                continue
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {"_raw": args_str}
            results.append(ToolCall(
                tool_name=func.get("name", ""),
                args=args,
                call_id=tc.get("id", ""),
                raw_block=tc,
            ))
        return results

    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        denied_ids = {tc.call_id for tc, _, _ in denials}
        denial_texts = []
        for tc, reason, rule in denials:
            denial_texts.append(
                f"[Governance] Operation denied: {tc.tool_name}\n"
                f"Reason: {reason}\n"
                f"Rule: {rule}\n"
                f"The operation was classified and denied by policy before execution."
            )

        choices = response_body.get("choices", [])
        if not choices:
            return response_body

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        # Filter out denied tool calls
        remaining = [tc for tc in tool_calls if tc.get("id") not in denied_ids]
        if remaining:
            message["tool_calls"] = remaining
        else:
            # All tool calls denied — remove tool_calls, add denial content
            message.pop("tool_calls", None)
            existing_content = message.get("content") or ""
            message["content"] = existing_content + "\n".join(denial_texts)
            choices[0]["finish_reason"] = "stop"

        return response_body

    def create_streaming_collector(self) -> "OpenAIStreamingCollector":
        return OpenAIStreamingCollector()


class OpenAIStreamingCollector(BaseStreamingCollector):
    """Collects tool calls from OpenAI SSE streams.

    OpenAI streams tool calls as delta.tool_calls[].function.arguments fragments.
    Tool calls are complete when finish_reason is "tool_calls".
    """

    def __init__(self):
        # Accumulate tool calls: {tc_index: {"id": ..., "name": ..., "arguments": ...}}
        self._pending: dict[int, dict] = {}
        # Buffered SSE events (all tool call events are buffered until finish)
        self._buffered_events: list[bytes] = []
        # Track the chunk index in the SSE stream for buffer association
        self._has_tool_calls = False

    def process_event(self, event_type: str, data: dict) -> StreamAction:
        # OpenAI uses "data:" lines without named event types; event_type may be empty
        if isinstance(data, str) and data == "[DONE]":
            return StreamAction(action="pass")

        choices = data.get("choices", [])
        if not choices:
            return StreamAction(action="pass")

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        tool_calls_delta = delta.get("tool_calls", [])
        if tool_calls_delta:
            self._has_tool_calls = True
            for tc_delta in tool_calls_delta:
                tc_idx = tc_delta.get("index", 0)
                if tc_idx not in self._pending:
                    self._pending[tc_idx] = {
                        "id": tc_delta.get("id", ""),
                        "name": "",
                        "arguments": "",
                    }
                if tc_delta.get("id"):
                    self._pending[tc_idx]["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    self._pending[tc_idx]["name"] = func["name"]
                if func.get("arguments"):
                    self._pending[tc_idx]["arguments"] += func["arguments"]
            return StreamAction(action="buffer")

        # Check for finish_reason == "tool_calls" — all pending are now complete
        if finish_reason == "tool_calls" and self._pending:
            # Return the first pending tool call; caller will get the rest
            # Actually, return all as a batch via completed_tool_call on idx 0
            # We use index=0 as a sentinel; the proxy should check all pending
            first_idx = min(self._pending.keys())
            first = self._pending[first_idx]
            try:
                args = json.loads(first["arguments"])
            except json.JSONDecodeError:
                args = {"_raw": first["arguments"]}
            tc = ToolCall(
                tool_name=first["name"],
                args=args,
                call_id=first["id"],
                raw_block=first,
            )
            return StreamAction(
                action="buffer",
                index=first_idx,
                completed_tool_call=tc,
            )

        if self._has_tool_calls:
            return StreamAction(action="buffer")

        return StreamAction(action="pass")

    def get_all_completed_tool_calls(self) -> list[ToolCall]:
        """Return all accumulated tool calls (called after finish_reason=tool_calls)."""
        results = []
        for tc_idx in sorted(self._pending.keys()):
            entry = self._pending[tc_idx]
            try:
                args = json.loads(entry["arguments"])
            except json.JSONDecodeError:
                args = {"_raw": entry["arguments"]}
            results.append(ToolCall(
                tool_name=entry["name"],
                args=args,
                call_id=entry["id"],
                raw_block=entry,
            ))
        return results

    def add_buffered_event(self, index: int, event_bytes: bytes) -> None:
        """Store a raw SSE event for later flush."""
        self._buffered_events.append(event_bytes)

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
        # Build an OpenAI-format SSE chunk with content instead of tool_calls
        chunk = {
            "choices": [{
                "index": 0,
                "delta": {"content": denial_text},
                "finish_reason": "stop",
            }],
        }
        return [f"data: {json.dumps(chunk)}\n\n".encode()]

    def get_buffered_events(self, index: int) -> list[bytes]:
        events = list(self._buffered_events)
        self._buffered_events.clear()
        return events
