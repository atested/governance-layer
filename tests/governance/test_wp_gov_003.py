"""WP-GOV-003 — policy classification and ALLOW/DENY contract fixtures."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from policy_contracts import (  # noqa: E402
    mediate_extracted_tool_call,
    validate_capability_entry,
    validate_mediated_decision,
    validate_policy_rule,
)


POLICY = {
    "base_dirs": [str(REPO)],
    "default_decision": "DENY",
    "default_reason": "No matched rule",
    "rules": [
        {"id": "read-repo", "match": {"action_type": ["read"], "target_within_base_dirs": True}, "decision": "ALLOW", "reason": "repository read"},
        {"id": "remote-deny", "match": {"scope": ["remote"]}, "decision": "DENY", "reason": "remote blocked"},
    ],
}


def test_allow_is_the_original_extracted_tool_call_without_governance_injection():
    call = {"name": "fs_read", "arguments": {"path": str(REPO / "README.md")}}
    result = mediate_extracted_tool_call(call, policy=POLICY, operator_identity="operator-1")
    assert result["decision"]["decision"] == "ALLOW"
    assert result["delivery"]["tool_call"] is call
    assert result["delivery"]["text"] is None


def test_deny_replaces_executable_call_with_machine_parsable_reason_and_rule():
    call = {"name": "Bash", "arguments": {"command": "curl https://example.invalid"}}
    result = mediate_extracted_tool_call(call, policy=POLICY)
    assert result["decision"]["decision"] == "DENY"
    assert result["delivery"]["tool_call"] is None
    assert "reason_code=V2_REMOTE_DENY" in result["delivery"]["text"]
    assert "matched_rule=remote-deny" in result["delivery"]["text"]


def test_decision_requires_completed_evaluation_and_reason_code_for_denial():
    decision = {
        "decision_id": "d1", "tool": "fs_read", "target": [], "operator_identity": "op",
        "confidence_tier": 1, "decision": "DENY", "matched_rule": "deny", "timestamp": "now",
        "policy_evaluation": {"completed": False},
    }
    failures = validate_mediated_decision(decision)
    assert "MEDIATED_DECISION_UNEVALUATED" in failures
    assert "MEDIATED_DECISION_DENY_REASON_CODE_REQUIRED" in failures
    decision["policy_evaluation"] = {"completed": True}
    decision["reason_code"] = "DENY_TEST"
    assert validate_mediated_decision(decision) == []


def test_policy_rule_and_capability_entry_contracts_reject_invalid_schema():
    assert "POLICY_RULE_INVALID_ACTION" in validate_policy_rule({
        "rule_id": "r", "condition": {}, "action": "sometimes", "reason_code": "R", "category": "test",
    })
    assert "CAPABILITY_ENTRY_INVALID_RISK_LEVEL" in validate_capability_entry({
        "tool": "fs_read", "risk_level": "unknown", "allowed_directories": ["/repo"],
        "constraint_flags": {}, "hard_caps": {},
    })


def test_supported_policy_rule_and_capability_entry_contracts_are_valid():
    assert validate_policy_rule({
        "rule_id": "read", "condition": {"action_type": ["read"]}, "action": "allow",
        "reason_code": "READ_ALLOWED", "category": "filesystem",
    }) == []
    assert validate_capability_entry({
        "tool": "fs_read", "risk_level": "MEDIUM", "allowed_directories": ["/repo"],
        "constraint_flags": {"deny_hidden_paths": True}, "hard_caps": {"max_bytes": 65536},
    }) == []
