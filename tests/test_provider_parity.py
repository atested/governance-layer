"""Provider parity tests.

Verifies that all four provider parsers (Anthropic, OpenAI, Gemini, LiteLLM)
produce identical governance behavior for equivalent tool calls.

Each test constructs the same logical tool call in each provider's native
response format, extracts ToolCall objects via the provider parser, and
verifies:
  1. Extracted tool_name and args are identical across providers
  2. Classification produces the same tier, action_type, and scope
  3. Policy evaluation produces the same ALLOW/DENY decision
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from proxy.providers.anthropic import AnthropicProvider
from proxy.providers.openai import OpenAIProvider
from proxy.providers.gemini import GeminiProvider
from proxy.providers.litellm import LiteLLMProvider
from proxy.providers.base import ToolCall

# Import classifier and policy evaluator
from scripts.classifier import classify
from scripts.policy_eval_v2 import evaluate, load_policy_rules

PROVIDERS = {
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "litellm": LiteLLMProvider(),
}

# Load policy once
POLICY = load_policy_rules()


def _anthropic_response(tool_name, args, call_id="tc_001"):
    """Build an Anthropic Messages API response body with one tool call."""
    return {
        "id": "msg_001",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": call_id, "name": tool_name, "input": args},
        ],
        "stop_reason": "tool_use",
    }


def _openai_response(tool_name, args, call_id="call_001"):
    """Build an OpenAI Chat Completions response body with one tool call."""
    return {
        "id": "chatcmpl-001",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def _gemini_response(tool_name, args):
    """Build a Gemini generateContent response body with one function call."""
    return {
        "candidates": [{
            "content": {
                "parts": [
                    {"functionCall": {"name": tool_name, "args": args}},
                ],
                "role": "model",
            },
            "finishReason": "STOP",
        }],
    }


# Test payloads: (tool_name, args, description)
TOOL_CALL_PAYLOADS = [
    # File read — should be Tier 1, ALLOW
    ("Read", {"file_path": "/src/app.js"}, "file_read"),
    # File write — should be Tier 1, may be ALLOW or DENY depending on base_dirs
    ("Write", {"file_path": "/src/app.js", "content": "hello"}, "file_write"),
    # Bash command — Tier 2 for well-known commands
    ("Bash", {"command": "git status"}, "bash_git_status"),
    # Bash command — Tier 3 for opaque scripts
    ("Bash", {"command": "python3 deploy.py"}, "bash_opaque_script"),
    # Unknown tool with file path evidence — should auto-classify
    ("MyCustomEditor", {"file_path": "/src/main.py", "action": "save"}, "unknown_with_path"),
    # Agent internal tool — should be ALLOW
    ("AskUserQuestion", {"question": "Which approach?"}, "agent_internal"),
    # Bash with network command — should classify as network
    ("Bash", {"command": "curl https://example.com/api"}, "bash_network"),
    # Sensitive path access
    ("Read", {"file_path": "/home/user/.ssh/id_rsa"}, "sensitive_path_read"),
]


def _extract_for_all_providers(tool_name, args):
    """Extract ToolCall from each provider's response format."""
    results = {}

    # Anthropic
    resp = _anthropic_response(tool_name, args)
    tcs = PROVIDERS["anthropic"].extract_tool_calls(resp)
    assert len(tcs) == 1, f"Anthropic: expected 1 tool call, got {len(tcs)}"
    results["anthropic"] = tcs[0]

    # OpenAI
    resp = _openai_response(tool_name, args)
    tcs = PROVIDERS["openai"].extract_tool_calls(resp)
    assert len(tcs) == 1, f"OpenAI: expected 1 tool call, got {len(tcs)}"
    results["openai"] = tcs[0]

    # Gemini
    resp = _gemini_response(tool_name, args)
    tcs = PROVIDERS["gemini"].extract_tool_calls(resp)
    assert len(tcs) == 1, f"Gemini: expected 1 tool call, got {len(tcs)}"
    results["gemini"] = tcs[0]

    # LiteLLM (same format as OpenAI)
    resp = _openai_response(tool_name, args)
    tcs = PROVIDERS["litellm"].extract_tool_calls(resp)
    assert len(tcs) == 1, f"LiteLLM: expected 1 tool call, got {len(tcs)}"
    results["litellm"] = tcs[0]

    return results


@pytest.mark.parametrize(
    "tool_name,args,desc",
    TOOL_CALL_PAYLOADS,
    ids=[p[2] for p in TOOL_CALL_PAYLOADS],
)
def test_extraction_parity(tool_name, args, desc):
    """All providers extract the same tool_name and args."""
    extracted = _extract_for_all_providers(tool_name, args)

    names = {p: tc.tool_name for p, tc in extracted.items()}
    args_out = {p: tc.args for p, tc in extracted.items()}

    # All providers must produce the same tool_name
    unique_names = set(names.values())
    assert len(unique_names) == 1, f"tool_name divergence: {names}"

    # All providers must produce the same args
    ref_args = args_out["anthropic"]
    for provider, provider_args in args_out.items():
        assert provider_args == ref_args, (
            f"args divergence ({provider} vs anthropic): "
            f"{provider_args} != {ref_args}"
        )


@pytest.mark.parametrize(
    "tool_name,args,desc",
    TOOL_CALL_PAYLOADS,
    ids=[p[2] for p in TOOL_CALL_PAYLOADS],
)
def test_classification_parity(tool_name, args, desc):
    """Classification produces identical results regardless of provider."""
    extracted = _extract_for_all_providers(tool_name, args)

    classifications = {}
    for provider, tc in extracted.items():
        result = classify(tc.tool_name, tc.args)
        classifications[provider] = result

    # Compare key classification fields across all providers
    ref = classifications["anthropic"]
    for provider, cls in classifications.items():
        assert cls["action_type"] == ref["action_type"], (
            f"action_type divergence ({provider}): "
            f"{cls['action_type']} != {ref['action_type']}"
        )
        assert cls["confidence_tier"] == ref["confidence_tier"], (
            f"confidence_tier divergence ({provider}): "
            f"{cls['confidence_tier']} != {ref['confidence_tier']}"
        )
        assert cls["scope"] == ref["scope"], (
            f"scope divergence ({provider}): "
            f"{cls['scope']} != {ref['scope']}"
        )
        assert cls.get("targets") == ref.get("targets"), (
            f"targets divergence ({provider}): "
            f"{cls.get('targets')} != {ref.get('targets')}"
        )


@pytest.mark.parametrize(
    "tool_name,args,desc",
    TOOL_CALL_PAYLOADS,
    ids=[p[2] for p in TOOL_CALL_PAYLOADS],
)
def test_policy_decision_parity(tool_name, args, desc):
    """Policy evaluation produces identical ALLOW/DENY across providers."""
    extracted = _extract_for_all_providers(tool_name, args)

    decisions = {}
    for provider, tc in extracted.items():
        classification = classify(tc.tool_name, tc.args)
        result = evaluate(classification, POLICY)
        decisions[provider] = {
            "decision": result["policy_decision"],
            "matched_rule": result.get("matched_rule", ""),
            "denial_reason": result.get("denial_reason", ""),
        }

    ref = decisions["anthropic"]
    for provider, dec in decisions.items():
        assert dec["decision"] == ref["decision"], (
            f"POLICY DECISION DIVERGENCE ({provider} vs anthropic): "
            f"{dec['decision']} != {ref['decision']} "
            f"[rule: {dec['matched_rule']} vs {ref['matched_rule']}]"
        )
        assert dec["matched_rule"] == ref["matched_rule"], (
            f"matched_rule divergence ({provider}): "
            f"{dec['matched_rule']} != {ref['matched_rule']}"
        )


def test_denial_format_consistency():
    """All providers produce denial text with the same key information."""
    tool_name = "Bash"
    args = {"command": "python3 deploy.py"}  # Tier 3 — should be denied

    for provider_name, provider in PROVIDERS.items():
        tc = ToolCall(
            tool_name=tool_name,
            args=args,
            call_id="test-001",
            raw_block={},
        )
        # Build denial events for streaming
        events = provider.create_streaming_collector().build_denial_events(
            index=0,
            tool_call=tc,
            reason="Operator approval required",
            matched_rule="tier3-approval-required",
        )
        # All providers should produce at least one event
        assert len(events) > 0, f"{provider_name}: no denial events produced"

        # Decode and verify denial text contains key information
        combined = b"".join(events).decode("utf-8")
        assert "Operation denied" in combined, (
            f"{provider_name}: denial text missing 'Operation denied'"
        )
        assert tool_name in combined, (
            f"{provider_name}: denial text missing tool name"
        )


def test_no_tool_calls_extraction():
    """All providers return empty list when no tool calls are present."""
    # Anthropic — text-only response
    anthropic_resp = {
        "content": [{"type": "text", "text": "Here is my answer."}],
        "stop_reason": "end_turn",
    }
    assert PROVIDERS["anthropic"].extract_tool_calls(anthropic_resp) == []

    # OpenAI — no tool_calls in message
    openai_resp = {
        "choices": [{"message": {"role": "assistant", "content": "Answer."}}],
    }
    assert PROVIDERS["openai"].extract_tool_calls(openai_resp) == []

    # Gemini — text-only parts
    gemini_resp = {
        "candidates": [{
            "content": {"parts": [{"text": "Answer."}], "role": "model"},
        }],
    }
    assert PROVIDERS["gemini"].extract_tool_calls(gemini_resp) == []

    # LiteLLM — same as OpenAI
    assert PROVIDERS["litellm"].extract_tool_calls(openai_resp) == []


def test_openai_responses_tool_call_extraction():
    """OpenAI Responses API function calls are parsed for mediation."""
    provider = PROVIDERS["openai"]
    resp = {
        "output": [{
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_1",
            "name": "Bash",
            "arguments": json.dumps({"command": "git rev-parse HEAD"}),
        }],
    }
    calls = provider.extract_tool_calls(resp)
    assert len(calls) == 1
    assert calls[0].tool_name == "Bash"
    assert calls[0].args == {"command": "git rev-parse HEAD"}


def test_openai_realtime_tool_call_extraction():
    """OpenAI Realtime WebSocket function-call events are parsed for mediation."""
    provider = PROVIDERS["openai"]
    event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "id": "item_1",
            "call_id": "call_1",
            "name": "Bash",
            "arguments": json.dumps({"command": "git rev-parse HEAD"}),
        },
    }
    calls = provider.extract_realtime_tool_calls(event)
    assert len(calls) == 1
    classification = classify(calls[0].tool_name, calls[0].args)
    decision = evaluate(classification, POLICY)
    assert decision["policy_decision"] == "DENY"
    assert decision["matched_rule"] == "tier3-approval-required"
