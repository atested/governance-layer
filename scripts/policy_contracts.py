"""Locked data contracts for extracted-tool policy mediation.

This module is deliberately dependency-free.  The contracts are shared by
the proxy and non-HTTP integrations, so callers can validate a decision
before a record is persisted or a provider response is released.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional


ALLOW = "ALLOW"
DENY = "DENY"
_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# These JSON-schema-shaped contracts are intentionally data, rather than
# implicit Python implementation details: downstream consumers conform to
# this surface and must not need to infer field names from record variants.
MEDIATED_DECISION_SCHEMA = {
    "title": "MediatedDecision",
    "required": (
        "decision_id", "tool", "target", "operator_identity",
        "confidence_tier", "decision", "matched_rule", "timestamp",
        "policy_evaluation",
    ),
    "decision_values": (ALLOW, DENY),
    "deny_requires": ("reason_code", "matched_rule"),
}

POLICY_RULE_SCHEMA = {
    "title": "PolicyRule",
    "required": ("rule_id", "condition", "action", "reason_code", "category"),
    "action_values": ("allow", "deny"),
}

CAPABILITY_ENTRY_SCHEMA = {
    "title": "CapabilityEntry",
    "required": ("tool", "risk_level", "allowed_directories", "constraint_flags", "hard_caps"),
    "risk_levels": tuple(sorted(_RISK_LEVELS)),
}


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_policy_rule(rule: Any) -> list[str]:
    """Return machine-readable contract failures for a PolicyRule."""
    if not isinstance(rule, dict):
        return ["POLICY_RULE_NOT_OBJECT"]
    failures = [
        "POLICY_RULE_MISSING_" + field.upper()
        for field in POLICY_RULE_SCHEMA["required"]
        if field not in rule
    ]
    for field in ("rule_id", "action", "reason_code", "category"):
        if field in rule and not _non_empty_string(rule[field]):
            failures.append("POLICY_RULE_MISSING_" + field.upper())
    if rule.get("action") not in POLICY_RULE_SCHEMA["action_values"]:
        failures.append("POLICY_RULE_INVALID_ACTION")
    if not isinstance(rule.get("condition"), dict):
        failures.append("POLICY_RULE_INVALID_CONDITION")
    if not _REASON_CODE.fullmatch(str(rule.get("reason_code", ""))):
        failures.append("POLICY_RULE_INVALID_REASON_CODE")
    return failures


def validate_capability_entry(entry: Any) -> list[str]:
    """Return machine-readable contract failures for a CapabilityEntry."""
    if not isinstance(entry, dict):
        return ["CAPABILITY_ENTRY_NOT_OBJECT"]
    failures = [
        "CAPABILITY_ENTRY_MISSING_" + field.upper()
        for field in CAPABILITY_ENTRY_SCHEMA["required"]
        if field not in entry
    ]
    if not _non_empty_string(entry.get("tool")):
        failures.append("CAPABILITY_ENTRY_INVALID_TOOL")
    if entry.get("risk_level") not in _RISK_LEVELS:
        failures.append("CAPABILITY_ENTRY_INVALID_RISK_LEVEL")
    if not isinstance(entry.get("allowed_directories"), (list, tuple)) or not all(
        _non_empty_string(path) for path in entry.get("allowed_directories", ())
    ):
        failures.append("CAPABILITY_ENTRY_INVALID_ALLOWED_DIRECTORIES")
    if not isinstance(entry.get("constraint_flags"), dict):
        failures.append("CAPABILITY_ENTRY_INVALID_CONSTRAINT_FLAGS")
    if not isinstance(entry.get("hard_caps"), dict):
        failures.append("CAPABILITY_ENTRY_INVALID_HARD_CAPS")
    return failures


def validate_mediated_decision(decision: Any) -> list[str]:
    """Return machine-readable contract failures for a MediatedDecision."""
    if not isinstance(decision, dict):
        return ["MEDIATED_DECISION_NOT_OBJECT"]
    failures = [
        "MEDIATED_DECISION_MISSING_" + field.upper()
        for field in MEDIATED_DECISION_SCHEMA["required"]
        if field not in decision or decision[field] in (None, "")
    ]
    if decision.get("decision") not in MEDIATED_DECISION_SCHEMA["decision_values"]:
        failures.append("MEDIATED_DECISION_INVALID_VERDICT")
    evaluation = decision.get("policy_evaluation")
    if not isinstance(evaluation, dict) or evaluation.get("completed") is not True:
        failures.append("MEDIATED_DECISION_UNEVALUATED")
    if decision.get("decision") == DENY:
        if not _REASON_CODE.fullmatch(str(decision.get("reason_code", ""))):
            failures.append("MEDIATED_DECISION_DENY_REASON_CODE_REQUIRED")
        if not _non_empty_string(decision.get("matched_rule")):
            failures.append("MEDIATED_DECISION_DENY_MATCHED_RULE_REQUIRED")
    return failures


def policy_rule_from_legacy(rule: dict) -> dict:
    """Expose an existing ordered evaluator rule through the locked contract."""
    action = str(rule.get("decision", "DENY")).lower()
    rule_id = str(rule.get("id", "__default__"))
    return {
        "rule_id": rule_id,
        "condition": deepcopy(rule.get("match", {})),
        "action": action,
        "reason_code": str(rule.get("reason_code") or "V2_" + rule_id.upper().replace("-", "_")),
        "category": str(rule.get("category") or "policy"),
    }


def decision_from_record(record: dict) -> dict:
    """Project a completed evaluator record onto the locked decision contract."""
    reasons = record.get("policy_reasons") or []
    reason_code = reasons[0].get("code", "") if reasons and isinstance(reasons[0], dict) else ""
    classification = record.get("classification") or {}
    return {
        "decision_id": record.get("request_id", ""),
        "tool": record.get("original_tool", ""),
        "target": list(classification.get("targets") or []),
        "operator_identity": record.get("user_identity") or "unattributed",
        "confidence_tier": classification.get("confidence_tier"),
        "decision": record.get("policy_decision"),
        "matched_rule": record.get("matched_rule", ""),
        "reason_code": reason_code,
        "timestamp": record.get("timestamp_utc", ""),
        "policy_evaluation": {
            "completed": True,
            "policy_rules_hash": record.get("policy_rules_hash", ""),
            "evidence": deepcopy(record.get("evidence") or {}),
        },
    }


def mediate_extracted_tool_call(
    tool_call: dict,
    *,
    policy: Optional[dict] = None,
    operator_identity: str = "",
) -> dict:
    """Classify one extracted call and return an ALLOW passthrough or DENY text.

    For ALLOW, ``delivery["tool_call"]`` is the exact input object (not a
    reconstructed copy).  For DENY, it is ``None`` so no executable call can
    leak alongside the explanation text.
    """
    if not isinstance(tool_call, dict):
        raise ValueError("EXTRACTED_TOOL_CALL_NOT_OBJECT")
    tool = tool_call.get("tool") or tool_call.get("name")
    args = tool_call.get("arguments", tool_call.get("args", {}))
    if not _non_empty_string(tool) or not isinstance(args, dict):
        raise ValueError("EXTRACTED_TOOL_CALL_INVALID")

    # Imports remain local so the contracts are usable by configuration tools
    # without modifying import paths or loading proxy dependencies.
    from classifier import classify
    from policy_eval_v2 import evaluate

    record = evaluate(
        classify(tool, args), policy=policy, user_identity=operator_identity,
    )
    decision = decision_from_record(record)
    failures = validate_mediated_decision(decision)
    if failures:
        raise ValueError(failures[0])
    if decision["decision"] == ALLOW:
        return {"decision": decision, "delivery": {"tool_call": tool_call, "text": None}}

    text = (
        "[Governance] Operation denied\n"
        f"reason_code={decision['reason_code']}\n"
        f"matched_rule={decision['matched_rule']}"
    )
    return {"decision": decision, "delivery": {"tool_call": None, "text": text}}
