"""
gemini.py — Google Gemini API provider for the Atested governance proxy.

Handles functionCall extraction, denial rewriting, and streaming collection
for the Gemini generateContent format.
"""

import json
from typing import Optional

from .base import BaseProvider, BaseStreamingCollector, StreamAction, ToolCall

GEMINI_DEFAULT_UPSTREAM = "https://generativelanguage.googleapis.com"


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini generateContent API."""

    name = "gemini"

    def get_upstream_url(self, path: str, config: dict) -> str:
        base = config.get("gemini_upstream", GEMINI_DEFAULT_UPSTREAM).rstrip("/")
        return f"{base}{path}"

    def forward_headers(self, request_headers: dict) -> dict:
        forwarded = {}
        for k, v in request_headers.items():
            kl = k.lower() if k != k.lower() else k
            if kl in ("x-goog-api-key", "content-type", "accept", "authorization"):
                forwarded[k] = v
        return forwarded

    def is_tool_endpoint(self, path: str) -> bool:
        path_base = path.split("?")[0]
        # Matches :generateContent and :streamGenerateContent
        return "GenerateContent" in path_base or "generateContent" in path_base

    def is_streaming(self, body: bytes) -> bool:
        # Gemini streaming uses streamGenerateContent in the URL path,
        # not a body flag. The proxy detects this at the routing level.
        # This method is called with the body, so we return False here;
        # streaming detection is handled by checking the URL path.
        return False

    def is_streaming_path(self, path: str) -> bool:
        """Check if the URL path indicates streaming (streamGenerateContent)."""
        return "streamGenerateContent" in path

    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        results = []
        candidates = response_body.get("candidates", [])
        if not candidates:
            return results
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        for i, part in enumerate(parts):
            fc = part.get("functionCall")
            if fc:
                results.append(ToolCall(
                    tool_name=fc.get("name", ""),
                    args=fc.get("args", {}),
                    call_id=f"gemini-fc-{i}",  # Gemini doesn't have native call IDs
                    raw_block=part,
                ))
        return results

    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        denied_names = {tc.call_id for tc, _, _ in denials}
        denial_map = {tc.call_id: (tc, reason, rule) for tc, reason, rule in denials}

        candidates = response_body.get("candidates", [])
        if not candidates:
            return response_body

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        new_parts = []
        for i, part in enumerate(parts):
            fc = part.get("functionCall")
            call_id = f"gemini-fc-{i}"
            if fc and call_id in denied_names:
                tc, reason, rule = denial_map[call_id]
                new_parts.append({
                    "text": (
                        f"[Governance] Operation denied: {tc.tool_name}\n"
                        f"Reason: {reason}\n"
                        f"Rule: {rule}\n"
                        f"The operation was classified and denied by policy before execution."
                    ),
                })
            else:
                new_parts.append(part)

        content["parts"] = new_parts
        return response_body

    def create_streaming_collector(self) -> "GeminiStreamingCollector":
        return GeminiStreamingCollector()


class GeminiStreamingCollector(BaseStreamingCollector):
    """Collects function calls from Gemini SSE streams.

    Gemini's streamGenerateContent typically delivers function calls
    complete in a single chunk, so collection is straightforward.
    """

    def __init__(self):
        self._buffered_events: dict[int, list[bytes]] = {}
        self._fc_counter = 0

    def process_event(self, event_type: str, data: dict) -> StreamAction:
        candidates = data.get("candidates", [])
        if not candidates:
            return StreamAction(action="pass")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        for part in parts:
            fc = part.get("functionCall")
            if fc:
                call_id = f"gemini-fc-{self._fc_counter}"
                self._fc_counter += 1
                tc = ToolCall(
                    tool_name=fc.get("name", ""),
                    args=fc.get("args", {}),
                    call_id=call_id,
                    raw_block=part,
                )
                return StreamAction(
                    action="buffer",
                    index=0,
                    completed_tool_call=tc,
                )

        return StreamAction(action="pass")

    def add_buffered_event(self, index: int, event_bytes: bytes) -> None:
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
        chunk = {
            "candidates": [{
                "content": {
                    "parts": [{"text": denial_text}],
                    "role": "model",
                },
            }],
        }
        return [f"data: {json.dumps(chunk)}\n\n".encode()]

    def get_buffered_events(self, index: int) -> list[bytes]:
        return self._buffered_events.pop(index, [])
