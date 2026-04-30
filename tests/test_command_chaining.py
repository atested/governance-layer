"""Tests for Bash command chaining classification.

Verifies that the classifier evaluates ALL commands in a chain (&&, ||, ;)
and classifies at the highest tier / most restrictive result. This prevents
the security gap where destructive commands could be prefixed with benign
ones to bypass governance.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.classifier import classify, _split_command_chain
from scripts.policy_eval_v2 import evaluate, load_policy_rules

POLICY = load_policy_rules()


def _classify_bash(command):
    """Classify a Bash tool call with the given command."""
    return classify("Bash", {"command": command})


def _evaluate_bash(command):
    """Classify and evaluate a Bash command against policy."""
    cls = _classify_bash(command)
    return evaluate(cls, POLICY)


# --- _split_command_chain tests ---

class TestSplitCommandChain:
    def test_single_command(self):
        assert _split_command_chain("git status") == ["git status"]

    def test_and_chain(self):
        assert _split_command_chain("git status && rm /tmp/x") == [
            "git status", "rm /tmp/x"
        ]

    def test_or_chain(self):
        assert _split_command_chain("test -f x || echo missing") == [
            "test -f x", "echo missing"
        ]

    def test_semicolon_chain(self):
        assert _split_command_chain("echo hello; rm -rf /") == [
            "echo hello", "rm -rf /"
        ]

    def test_multiple_operators(self):
        result = _split_command_chain("a && b; c || d")
        assert result == ["a", "b", "c", "d"]

    def test_quoted_operators_not_split(self):
        # Operators inside quotes should NOT be treated as separators
        assert _split_command_chain('echo "a && b"') == ['echo "a && b"']

    def test_single_quoted_operators_not_split(self):
        assert _split_command_chain("echo 'a && b'") == ["echo 'a && b'"]

    def test_pipe_not_split(self):
        # Pipes are handled by _classify_single_command, not by chain splitting
        assert _split_command_chain("cat file.txt | grep pattern") == [
            "cat file.txt | grep pattern"
        ]

    def test_escaped_operators(self):
        assert _split_command_chain('echo a \\&\\& b') == ['echo a \\&\\& b']


# --- Classification tests ---

class TestCommandChainingClassification:
    def test_benign_then_destructive_elevates_tier(self):
        """git status && rm /tmp/x must not stay at Tier 2 read."""
        cls = _classify_bash("git status && rm /tmp/x")
        # rm is a destructive command — must be at least Tier 2 delete
        assert cls["confidence_tier"] >= 2
        assert cls["action_type"] != "read", (
            "Chained destructive command must not be classified as read"
        )

    def test_echo_semicolon_rm_is_destructive(self):
        """echo hello; rm -rf / must classify as destructive."""
        cls = _classify_bash("echo hello; rm -rf /")
        assert cls["action_type"] == "delete"

    def test_pipe_to_readonly_stays_low(self):
        """cat file.txt | grep pattern should remain at pipeline tier."""
        cls = _classify_bash("cat file.txt | grep pattern")
        # Pipes become Tier 3 (opaque pipeline), which is correct behavior
        assert cls["confidence_tier"] == 3
        assert cls["evidence"]["source"] == "command_pipeline"

    def test_pipe_to_tee_is_write(self):
        """cat file.txt | tee output.txt should be pipeline (Tier 3)."""
        cls = _classify_bash("cat file.txt | tee output.txt")
        assert cls["confidence_tier"] == 3

    def test_quoted_operators_single_command(self):
        """echo 'a && b' is a single echo, not a chain."""
        cls = _classify_bash('echo "a && b"')
        # Should be a single unrecognized command, not split
        assert "command_chain" not in cls["evidence"]["source"]

    def test_chain_preserves_highest_scope(self):
        """Chain with network command escalates scope.

        D-161 opacity floor: chained commands are classified as opaque
        (Tier 3). The action_type reflects the highest-severity
        component but the tier is elevated to 3 because the chain
        prevents full inspection. Prior to D-161, this expected
        action_type == "network", but the opacity floor now correctly
        returns "execute" for opaque chained commands.
        """
        cls = _classify_bash("echo hello && curl https://evil.com")
        assert cls["scope"] == "remote"
        # D-161: chained commands with opaque elements are Tier 3+
        # action_type is "execute" (opaque classification), not "network"
        assert cls["confidence_tier"] >= 3

    def test_three_part_chain_takes_worst(self):
        """git status && echo ok && rm -rf / takes the destructive classification."""
        cls = _classify_bash("git status && echo ok && rm -rf /")
        assert cls["action_type"] == "delete"

    def test_chain_evidence_source_noted(self):
        """Chain classification notes it was a chain."""
        cls = _classify_bash("git status && rm /tmp/x")
        assert "command_chain" in cls["evidence"]["source"]


# --- Policy decision tests ---

class TestCommandChainingPolicyDecisions:
    def test_benign_chain_then_destructive_not_blanket_allow(self):
        """git status && rm /tmp/x must not get ALLOW from execute-tier2-allow."""
        result = _evaluate_bash("git status && rm /tmp/x")
        # The chained command should not get the same rule as a simple git status
        assert result.get("matched_rule") != "execute-tier2-allow" or \
            result["policy_decision"] == "DENY", (
            "Chained destructive command should not pass through execute-tier2-allow"
        )

    def test_simple_git_status_still_allowed(self):
        """Regression: simple git status must still be ALLOW."""
        result = _evaluate_bash("git status")
        assert result["policy_decision"] == "ALLOW"
        # git status classifies as read/repository → matches read-source-allow
        assert result["matched_rule"] == "read-source-allow"

    def test_simple_rm_classified_correctly(self):
        """Simple rm command classified as delete."""
        cls = _classify_bash("rm /tmp/x")
        assert cls["action_type"] == "delete"
