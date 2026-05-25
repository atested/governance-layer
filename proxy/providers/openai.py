"""
openai.py — OpenAI API provider for the Atested governance proxy.

Handles tool_calls/function_call extraction, denial rewriting, and streaming
collection for OpenAI Chat Completions and Responses API formats.
"""

import json
from typing import Optional

from .base import BaseProvider, BaseStreamingCollector, StreamAction, ToolCall

OPENAI_DEFAULT_UPSTREAM = "https://api.openai.com"


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI Chat Completions and Responses APIs."""

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
        normalized = path_base.rstrip("/")
        return normalized.endswith("/v1/chat/completions") or normalized.endswith("/v1/responses")

    def is_streaming(self, body: bytes) -> bool:
        try:
            return json.loads(body).get("stream", False)
        except (json.JSONDecodeError, AttributeError):
            return False

    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        if "output" in response_body:
            return self._extract_responses_tool_calls(response_body)
        return self._extract_chat_tool_calls(response_body)

    def response_format_known(self, response_body: dict) -> bool:
        return "choices" in response_body or "output" in response_body or "error" in response_body

    def _extract_chat_tool_calls(self, response_body: dict) -> list[ToolCall]:
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
                response_format="chat_completions",
            ))
        return results

    def _extract_responses_tool_calls(self, response_body: dict) -> list[ToolCall]:
        results = []
        output = response_body.get("output", [])
        if not isinstance(output, list):
            return results
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            args_str = item.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else {}
            except json.JSONDecodeError:
                args = {"_raw": args_str}
            results.append(ToolCall(
                tool_name=item.get("name", ""),
                args=args,
                call_id=item.get("call_id") or item.get("id", ""),
                raw_block=item,
                response_format="responses",
            ))
        return results

    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        if "output" in response_body or any(tc.response_format == "responses" for tc, _, _ in denials):
            return self._apply_responses_denials(response_body, denials)
        return self._apply_chat_denials(response_body, denials)

    def _apply_chat_denials(
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

    def _apply_responses_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        denied_ids = {tc.call_id for tc, _, _ in denials}
        denial_map = {tc.call_id: (tc, reason, rule) for tc, reason, rule in denials}
        new_output = []
        for item in response_body.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "function_call":
                new_output.append(item)
                continue
            call_id = item.get("call_id") or item.get("id", "")
            if call_id not in denied_ids:
                new_output.append(item)
                continue
            tc, reason, rule = denial_map[call_id]
            denial_text = (
                f"[Governance] Operation denied: {tc.tool_name}\n"
                f"Reason: {reason}\n"
                f"Rule: {rule}\n"
                f"The operation was classified and denied by policy before execution."
            )
            new_output.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": denial_text}],
            })
        response_body["output"] = new_output
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
        self._responses_pending: dict[int, dict] = {}
        self._responses_item_to_index: dict[str, int] = {}

    def process_event(self, event_type: str, data: dict) -> StreamAction:
        if self._looks_like_responses_event(event_type, data):
            return self._process_responses_event(event_type, data)
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

    @staticmethod
    def _looks_like_responses_event(event_type: str, data: dict) -> bool:
        data_type = data.get("type", "") if isinstance(data, dict) else ""
        return (
            event_type.startswith("response.")
            or str(data_type).startswith("response.")
            or data.get("object") == "response"
        )

    def _process_responses_event(self, event_type: str, data: dict) -> StreamAction:
        data_type = str(data.get("type") or event_type)
        item = data.get("item") if isinstance(data.get("item"), dict) else {}
        output_index = data.get("output_index")
        if output_index is None and isinstance(item, dict):
            output_index = item.get("output_index")
        try:
            idx = int(output_index) if output_index is not None else len(self._responses_pending)
        except (TypeError, ValueError):
            idx = len(self._responses_pending)

        if data_type in {"response.output_item.added", "response.output_item.done"} and item.get("type") == "function_call":
            entry = self._responses_pending.setdefault(idx, {
                "id": item.get("id", ""),
                "call_id": item.get("call_id") or item.get("id", ""),
                "name": "",
                "arguments": "",
            })
            if item.get("id"):
                self._responses_item_to_index[item["id"]] = idx
                entry["id"] = item["id"]
            if item.get("call_id"):
                entry["call_id"] = item["call_id"]
            if item.get("name"):
                entry["name"] = item["name"]
            if item.get("arguments"):
                entry["arguments"] = item["arguments"]
            self._has_tool_calls = True
            if data_type == "response.output_item.done":
                return self._complete_responses_tool_call(idx, entry)
            return StreamAction(action="buffer", index=idx)

        if data_type in {"response.function_call_arguments.delta", "response.function_call_arguments.done"}:
            item_id = data.get("item_id")
            if isinstance(item_id, str) and item_id in self._responses_item_to_index:
                idx = self._responses_item_to_index[item_id]
            entry = self._responses_pending.setdefault(idx, {
                "id": item_id or "",
                "call_id": data.get("call_id") or item_id or "",
                "name": data.get("name") or "",
                "arguments": "",
            })
            if data.get("delta"):
                entry["arguments"] += str(data.get("delta"))
            if data.get("arguments"):
                entry["arguments"] = str(data.get("arguments"))
            self._has_tool_calls = True
            if data_type == "response.function_call_arguments.done":
                return self._complete_responses_tool_call(idx, entry)
            return StreamAction(action="buffer", index=idx)

        if self._has_tool_calls:
            return StreamAction(action="buffer", index=idx)
        return StreamAction(action="pass")

    @staticmethod
    def _complete_responses_tool_call(idx: int, entry: dict) -> StreamAction:
        args_str = entry.get("arguments") or "{}"
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {"_raw": args_str}
        tc = ToolCall(
            tool_name=entry.get("name", ""),
            args=args,
            call_id=entry.get("call_id") or entry.get("id", ""),
            raw_block={
                "type": "function_call",
                "id": entry.get("id", ""),
                "call_id": entry.get("call_id") or entry.get("id", ""),
                "name": entry.get("name", ""),
                "arguments": args_str,
            },
            response_format="responses",
        )
        return StreamAction(action="buffer", index=idx, completed_tool_call=tc)

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
        if tool_call.response_format == "responses":
            chunk = {
                "type": "response.output_text.delta",
                "delta": denial_text,
            }
            return [f"event: response.output_text.delta\ndata: {json.dumps(chunk)}\n\n".encode()]
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
