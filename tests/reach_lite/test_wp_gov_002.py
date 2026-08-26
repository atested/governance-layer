"""WP-GOV-002 — identify every tool-call block in a model response for
classification while passing text blocks through unmodified, including in
streaming responses.

The per-provider streaming collector is the component that inspects a
streaming model response block-by-block. This test drives the OpenAI
compatible collector (inherited by Ollama's OpenAI-compatible path) through
a realistic SSE sequence and asserts the WP-GOV-002 contract:

* a text-only delta block is passed through unmodified (action == "pass");
* tool-call fragment blocks are buffered (action == "buffer");
* the terminal ``finish_reason == "tool_calls"`` block surfaces a completed
  ToolCall for governance classification (``completed_tool_call`` is set),
  carrying the tool name, reassembled arguments, and provider call id.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROXY_DIR = REPO / "proxy"
if str(PROXY_DIR) not in sys.path:
    sys.path.insert(0, str(PROXY_DIR))

from proxy.providers.openai import OpenAIStreamingCollector  # noqa: E402
from proxy.providers.gemini import GeminiStreamingCollector  # noqa: E402


def _collector() -> OpenAIStreamingCollector:
    return OpenAIStreamingCollector()


def _text(content: str):
    return {"choices": [{"delta": {"content": content}, "finish_reason": None}]}


def _tool_tc(index, tc):
    return {"choices": [{"delta": {"tool_calls": [dict({"index": index}, **tc)]}, "finish_reason": None}]}


def _finish():
    return {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}


def test_streaming_text_block_passes_through_unmodified():
    c = _collector()
    action = c.process_event("", _text("Hello, how can I help?"))
    assert action.action == "pass"
    assert action.completed_tool_call is None


def test_streaming_tool_call_block_identified_for_classification():
    c = _collector()
    a1 = c.process_event("", _tool_tc(0, {"id": "call_abc", "function": {"name": "get_weather"}}))
    assert a1.action == "buffer"
    a2 = c.process_event("", _tool_tc(0, {"function": {"arguments": '{"city":'}}))
    assert a2.action == "buffer"
    a3 = c.process_event("", _tool_tc(0, {"function": {"arguments": '"NYC"}'}}))
    assert a3.action == "buffer"
    # Partial blocks stay buffered and cannot reach classification or output.
    assert a3.all_completed_tool_calls() == ()
    # Terminal block signals the tool call is complete -> surfaced for classification.
    a4 = c.process_event("", _finish())
    assert a4.action == "buffer"
    tc = a4.completed_tool_call
    assert tc is not None
    assert tc.tool_name == "get_weather"
    assert tc.args == {"city": "NYC"}
    assert tc.call_id == "call_abc"


def test_streaming_text_and_tool_blocks_together():
    c = _collector()
    # Leading text block passes through unmodified.
    t = c.process_event("", _text("Sure, checking the weather now."))
    assert t.action == "pass"
    # Then a tool-call block is identified and surfaced for classification.
    c.process_event("", _tool_tc(0, {"id": "call_xyz", "function": {"name": "lookup"}}))
    c.process_event("", _tool_tc(0, {"function": {"arguments": "{}"}}))
    done = c.process_event("", _finish())
    assert done.action == "buffer"
    assert done.completed_tool_call is not None
    assert done.completed_tool_call.tool_name == "lookup"
    assert done.completed_tool_call.args == {}
    assert done.completed_tool_call.call_id == "call_xyz"


def test_streaming_text_after_a_tool_fragment_still_passes_through():
    c = _collector()
    c.process_event("", _tool_tc(0, {"id": "call_xyz", "function": {"name": "lookup"}}))

    text = _text("I can explain the result while it is prepared.")
    action = c.process_event("", text)

    assert action.action == "pass"
    assert action.all_completed_tool_calls() == ()


def test_responses_text_after_a_tool_call_still_passes_through():
    c = _collector()
    c.process_event("response.output_item.added", {
        "type": "response.output_item.added",
        "output_index": 0,
        "item": {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "lookup"},
    })

    text = {
        "type": "response.output_text.delta",
        "output_index": 1,
        "delta": "The lookup is in progress.",
    }
    action = c.process_event("response.output_text.delta", text)

    assert action.action == "pass"
    assert action.all_completed_tool_calls() == ()


def test_streaming_identifies_every_completed_tool_call_for_classification():
    c = _collector()
    c.process_event("", _tool_tc(0, {"id": "call_read", "function": {"name": "read"}}))
    c.process_event("", _tool_tc(1, {"id": "call_write", "function": {"name": "write"}}))
    c.process_event("", _tool_tc(0, {"function": {"arguments": '{"path":"a"}'}}))
    c.process_event("", _tool_tc(1, {"function": {"arguments": '{"path":"b"}'}}))

    done = c.process_event("", _finish())

    assert [call.call_id for call in done.all_completed_tool_calls()] == [
        "call_read",
        "call_write",
    ]
    assert [call.args for call in done.all_completed_tool_calls()] == [
        {"path": "a"},
        {"path": "b"},
    ]


def test_streaming_preserves_unparseable_arguments_without_misextracting_them():
    c = _collector()
    c.process_event("", _tool_tc(0, {"id": "call_raw", "function": {"name": "write"}}))
    c.process_event("", _tool_tc(0, {"function": {"arguments": '{"path":'}}))

    done = c.process_event("", _finish())

    assert done.all_completed_tool_calls()[0].args == {"_raw": '{"path":'}


def test_gemini_streaming_identifies_every_tool_call_in_one_block():
    collector = GeminiStreamingCollector()
    data = {
        "candidates": [{
            "content": {"parts": [
                {"functionCall": {"name": "read", "args": {"path": "a"}}},
                {"text": "working"},
                {"functionCall": {"name": "write", "args": {"path": "b"}}},
            ]},
        }],
    }

    action = collector.process_event("", data)

    assert action.action == "buffer"
    assert [call.tool_name for call in action.all_completed_tool_calls()] == ["read", "write"]
    assert [call.args for call in action.all_completed_tool_calls()] == [
        {"path": "a"},
        {"path": "b"},
    ]
