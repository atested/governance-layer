"""Provider-response release boundary.

This module deliberately completes inspection and classification of every
proposed call before constructing the agent-visible response.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from proxy.providers.base import BaseProvider, ToolCall


@dataclass(frozen=True)
class GovernedResponse:
    body: dict
    decisions: tuple[tuple[ToolCall, dict], ...]
    observations: tuple[dict, ...]


def govern_provider_response(
    provider: BaseProvider,
    response_body: dict,
    decide: Callable[[ToolCall], dict],
) -> GovernedResponse:
    """Inspect all calls, classify each once, then release or replace.

    The input is deep-copied so the original provider response remains useful
    as evidence.  No release observation can exist until the complete call set
    has been inspected and classified.
    """
    original = deepcopy(response_body)
    tool_calls = provider.extract_tool_calls(original)
    observations: list[dict] = [{
        "event": "response_inspected",
        "proposed_call_count": len(tool_calls),
    }]
    decisions: list[tuple[ToolCall, dict]] = []

    for index, tool_call in enumerate(tool_calls):
        observations.append({
            "event": "call_inspected",
            "call_id": tool_call.call_id,
            "index": index,
        })
        record = decide(tool_call)
        decisions.append((tool_call, record))
        observations.append({
            "event": "call_classified",
            "call_id": tool_call.call_id,
            "index": index,
            "decision": record.get("policy_decision", "DENY"),
        })

    denials: list[tuple[ToolCall, str, str]] = []
    for tool_call, record in decisions:
        if record.get("policy_decision") != "ALLOW":
            reasons = record.get("policy_reasons") or []
            detail = reasons[0].get("detail", {}) if reasons else {}
            reason = detail.get("reason", "policy denied") if isinstance(detail, dict) else str(detail)
            denials.append((tool_call, reason, record.get("matched_rule", "")))

    released = provider.apply_denials(deepcopy(original), denials) if denials else original
    observations.append({
        "event": "response_released",
        "proposed_call_count": len(tool_calls),
        "classified_call_count": len(decisions),
        "denied_call_count": len(denials),
    })
    return GovernedResponse(
        body=released,
        decisions=tuple(decisions),
        observations=tuple(observations),
    )
