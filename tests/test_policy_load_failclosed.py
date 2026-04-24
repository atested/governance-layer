"""Tests for policy-rules.json load failure handling (fail-closed).

Verifies that malformed, missing, or invalid policy files result in
deny-all behavior rather than crashes or unhandled exceptions.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from policy_eval_v2 import load_policy_rules, evaluate


def _make_tmp_file(content: str, suffix=".json") -> Path:
    """Write content to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, dir="/private/tmp/claude-501"
    )
    f.write(content)
    f.close()
    return Path(f.name)


class TestPolicyLoadFailClosed:
    def test_missing_file_returns_deny_all(self):
        """Missing policy file → deny-all, no crash."""
        rules = load_policy_rules(Path("/nonexistent/policy-rules.json"))
        assert rules["rules"] == []
        assert rules.get("_fallback") is True

    def test_malformed_json_returns_deny_all(self):
        """Invalid JSON → deny-all, no crash."""
        p = _make_tmp_file("{invalid json!!!")
        try:
            rules = load_policy_rules(p)
            assert rules["rules"] == []
            assert rules.get("_fallback") is True
        finally:
            p.unlink()

    def test_wrong_structure_returns_deny_all(self):
        """Valid JSON but wrong structure → deny-all."""
        p = _make_tmp_file('["not", "a", "dict"]')
        try:
            rules = load_policy_rules(p)
            assert rules["rules"] == []
        finally:
            p.unlink()

    def test_missing_rules_key_returns_deny_all(self):
        """Dict without 'rules' key → deny-all."""
        p = _make_tmp_file('{"version": 1}')
        try:
            rules = load_policy_rules(p)
            assert rules["rules"] == []
        finally:
            p.unlink()

    def test_rules_not_list_returns_deny_all(self):
        """'rules' key is not a list → deny-all."""
        p = _make_tmp_file('{"rules": "not_a_list"}')
        try:
            rules = load_policy_rules(p)
            assert rules["rules"] == []
        finally:
            p.unlink()

    def test_valid_file_loads_normally(self):
        """Valid policy file loads without fallback flag."""
        p = _make_tmp_file(json.dumps({"rules": []}))
        try:
            rules = load_policy_rules(p)
            assert rules["rules"] == []
            assert "_fallback" not in rules
        finally:
            p.unlink()

    def test_deny_all_policy_denies_everything(self):
        """A deny-all policy (empty rules) results in DENY for any classification."""
        rules = load_policy_rules(Path("/nonexistent/policy-rules.json"))
        classification = {
            "action_type": "read",
            "targets": ["/tmp/test.txt"],
            "scope": "local",
            "confidence_tier": 1,
            "evidence": {"source": "test", "details": {}},
            "original_tool": "Read",
        }
        result = evaluate(classification, rules)
        assert result["policy_decision"] == "DENY"

    def test_default_path_loads_successfully(self):
        """The actual policy-rules.json in the repo loads without error."""
        rules = load_policy_rules()
        assert isinstance(rules["rules"], list)
        assert len(rules["rules"]) > 0
        assert "_fallback" not in rules
