"""
ollama.py — Ollama provider for the Atested governance proxy.

Ollama runs locally (default http://localhost:11434) and exposes two chat
APIs:

  * ``/v1/chat/completions`` — OpenAI-compatible Chat Completions surface.
    Request/response shapes match OpenAI exactly, so the OpenAI extractor,
    denial rewriter, and streaming SSE collector are reused via inheritance.
    This is the recommended path for tool-call mediation.

  * ``/api/chat`` — Ollama's native chat surface. Non-streaming responses
    return a single JSON object shaped like
    ``{"message": {"role": "assistant", "tool_calls": [...]}}`` with
    ``tool_calls[].function.arguments`` as an object rather than a JSON
    string. We extract and rewrite tool calls natively for non-streaming
    responses (``stream=false``).

Known limitation (QS-059): Ollama's native ``/api/chat`` streams as NDJSON
(one JSON object per line, no ``event:``/``data:`` framing), which is not
compatible with the proxy's SSE-based streaming collector. Tool-call
mediation on streaming ``/api/chat`` is therefore not supported in this
release — clients that need tool mediation against a local Ollama instance
should use the OpenAI-compatible ``/v1/chat/completions`` path. Streaming
``/api/chat`` requests are still routed to Ollama, but the SSE parser will
silently drop the NDJSON lines; the governance chain still records the
request via ``proxy_request_observed``.
"""

import json

from .base import ToolCall
from .openai import OpenAIProvider

OLLAMA_DEFAULT_UPSTREAM = "http://localhost:11434"


class OllamaProvider(OpenAIProvider):
    """Provider for a local Ollama server.

    Inherits the OpenAI Chat Completions parser and streaming collector,
    which fully covers the OpenAI-compatible ``/v1/chat/completions`` path.
    Adds a native extractor and denial rewriter for ``/api/chat``
    non-streaming responses.
    """

    name = "ollama"

    def get_upstream_url(self, path: str, config: dict) -> str:
        base = config.get("ollama_upstream", OLLAMA_DEFAULT_UPSTREAM).rstrip("/")
        return f"{base}{path}"

    def forward_headers(self, request_headers: dict) -> dict:
        """Ollama doesn't speak OpenAI-organization or OpenAI-project headers.

        Forward only the headers Ollama actually consumes: content-type and
        accept for body/format negotiation, and authorization in case the
        operator has put a reverse proxy with auth in front of Ollama.
        """
        forwarded = {}
        for k, v in request_headers.items():
            kl = k.lower() if k != k.lower() else k
            if kl in ("authorization", "content-type", "accept"):
                forwarded[k] = v
        return forwarded

    def is_tool_endpoint(self, path: str) -> bool:
        path_base = path.split("?")[0]
        normalized = path_base.rstrip("/")
        return (
            normalized.endswith("/v1/chat/completions")
            or normalized.endswith("/api/chat")
        )

    def extract_tool_calls(self, response_body: dict) -> list[ToolCall]:
        # OpenAI-compatible shape has ``choices`` at top level. The native
        # /api/chat shape has ``message`` at top level (no ``choices``).
        if "choices" in response_body or "output" in response_body:
            return super().extract_tool_calls(response_body)
        if "message" in response_body:
            return self._extract_native_tool_calls(response_body)
        return []

    def response_format_known(self, response_body: dict) -> bool:
        # Recognise OpenAI-compatible shapes (delegated to parent) plus
        # Ollama-native /api/chat responses.
        if super().response_format_known(response_body):
            return True
        return "message" in response_body

    def _extract_native_tool_calls(self, response_body: dict) -> list[ToolCall]:
        """Extract tool calls from Ollama's native /api/chat response shape.

        Native shape::

            {
              "model": "qwen2.5:7b",
              "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                  {"function": {"name": "Read",
                                "arguments": {"file_path": "/tmp/x"}}}
                ]
              },
              "done": true
            }

        Notes vs OpenAI:
          * No ``id`` on the tool call — we synthesize ``ollama-tc-<i>``.
          * ``arguments`` is an object, not a JSON-encoded string. We still
            tolerate a string for forward-compatibility.
          * No ``type`` discriminator on the tool call entry.
        """
        results: list[ToolCall] = []
        message = response_body.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        for i, tc in enumerate(tool_calls):
            func = tc.get("function") or {}
            args_raw = func.get("arguments")
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {"_raw": args_raw}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}
            call_id = tc.get("id") or f"ollama-tc-{i}"
            results.append(ToolCall(
                tool_name=func.get("name", ""),
                args=args,
                call_id=call_id,
                raw_block=tc,
                response_format="ollama_native",
            ))
        return results

    def apply_denials(
        self,
        response_body: dict,
        denials: list[tuple[ToolCall, str, str]],
    ) -> dict:
        # Route by response shape: OpenAI-compatible vs native.
        if "choices" in response_body or "output" in response_body:
            return super().apply_denials(response_body, denials)
        if "message" in response_body:
            return self._apply_native_denials(response_body, denials)
        return response_body

    def _apply_native_denials(
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

        message = response_body.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        remaining = []
        for i, tc in enumerate(tool_calls):
            call_id = tc.get("id") or f"ollama-tc-{i}"
            if call_id not in denied_ids:
                remaining.append(tc)

        if remaining:
            message["tool_calls"] = remaining
        else:
            # All tool calls denied — strip tool_calls, surface denial text in
            # the assistant message, and set done_reason so the client treats
            # the turn as terminated.
            message.pop("tool_calls", None)
            existing_content = message.get("content") or ""
            message["content"] = existing_content + "\n".join(denial_texts)
            response_body["done_reason"] = "stop"

        return response_body
