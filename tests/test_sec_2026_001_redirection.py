"""SEC-2026-001 — Shell redirection to sensitive paths must be DENIED.

Dispatch 180-D-2026-0430 (RELEASE-G4-BLOCKER-FIX)

Root cause: The classifier treated commands with > redirection as Tier 2
inferred writes. The policy evaluator skipped path validation on the full
command string (contains spaces), so the redirection destination was never
checked against base directories or sensitive path rules.

Fix: Added shell redirection operators to the classifier's opacity floor.
Any command containing >, >>, 2>, &>, >|, or < is now classified at
Tier 3 (TIER_OPAQUE) minimum, consistent with pipes, subshells, and
variable expansion.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from classifier import classify, TIER_OPAQUE, TIER_INFERRED
from policy_eval_v2 import evaluate


# ---------------------------------------------------------------------------
# Adversarial: redirection to sensitive paths must be DENIED
# ---------------------------------------------------------------------------

class TestRedirectionDenied:
    """Every redirection command must be DENIED (SEC-2026-001)."""

    def test_echo_to_etc_passwd(self):
        c = classify("Bash", {"command": "echo x > /etc/passwd"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_printf_to_ssh_authorized_keys(self):
        c = classify("Bash", {"command": "printf key > ~/.ssh/authorized_keys"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_cat_redirect_to_tmp(self):
        c = classify("Bash", {"command": "cat /etc/passwd > /tmp/out"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_stderr_redirect_to_etc_shadow(self):
        c = classify("Bash", {"command": "cmd 2> /etc/shadow"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_append_redirect_to_dotenv(self):
        c = classify("Bash", {"command": "cmd >> .env"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_redirect_outside_base_dir(self):
        c = classify("Bash", {"command": "cmd > ../outside-base-dir"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_combined_redirect_to_sensitive(self):
        c = classify("Bash", {"command": "cmd &> /tmp/sensitive"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"

    def test_clobber_redirect_to_etc_hosts(self):
        c = classify("Bash", {"command": "cmd >| /etc/hosts"})
        e = evaluate(c)
        assert c["confidence_tier"] >= TIER_OPAQUE
        assert e["policy_decision"] == "DENY"


# ---------------------------------------------------------------------------
# Positive: commands WITHOUT redirection classify normally (no regression)
# ---------------------------------------------------------------------------

class TestNoRedirectionRegression:
    """Commands without redirection operators must not be affected."""

    def test_git_status_still_tier2(self):
        c = classify("Bash", {"command": "git status"})
        assert c["confidence_tier"] == TIER_INFERRED
        e = evaluate(c)
        assert e["policy_decision"] == "ALLOW"

    def test_git_diff_still_tier2(self):
        c = classify("Bash", {"command": "git diff HEAD"})
        assert c["confidence_tier"] == TIER_INFERRED
        e = evaluate(c)
        assert e["policy_decision"] == "ALLOW"

    def test_git_log_still_tier2(self):
        c = classify("Bash", {"command": "git log --oneline -5"})
        assert c["confidence_tier"] == TIER_INFERRED
        e = evaluate(c)
        assert e["policy_decision"] == "ALLOW"

    def test_npm_install_still_tier2(self):
        c = classify("Bash", {"command": "npm install"})
        assert c["confidence_tier"] == TIER_INFERRED

    def test_plain_echo_is_not_redirect(self):
        """echo without > should not be caught by redirect pattern."""
        c = classify("Bash", {"command": "echo hello world"})
        source = c.get("evidence", {}).get("source", "")
        assert "redirection" not in source

    def test_heredoc_not_regressed(self):
        """<< (heredoc) should still classify at Tier 3+."""
        c = classify("Bash", {"command": "cat <<EOF\nhello\nEOF"})
        assert c["confidence_tier"] >= TIER_OPAQUE

    def test_process_substitution_not_regressed(self):
        """<( and >( should still classify at Tier 3+."""
        c = classify("Bash", {"command": "diff <(cmd1) <(cmd2)"})
        assert c["confidence_tier"] >= TIER_OPAQUE


# ---------------------------------------------------------------------------
# Opacity floor integration: redirection tagged in evidence source
# ---------------------------------------------------------------------------

class TestRedirectionOpacityTag:
    """Redirection opacity floor adds 'redirection' to evidence source."""

    def test_redirect_tagged_in_evidence(self):
        c = classify("Bash", {"command": "echo test > /tmp/file"})
        source = c.get("evidence", {}).get("source", "")
        assert "redirection" in source

    def test_stderr_redirect_tagged(self):
        c = classify("Bash", {"command": "cmd 2> /dev/null"})
        source = c.get("evidence", {}).get("source", "")
        assert "redirection" in source

    def test_append_redirect_tagged(self):
        c = classify("Bash", {"command": "cmd >> /tmp/log"})
        source = c.get("evidence", {}).get("source", "")
        assert "redirection" in source

    def test_clobber_redirect_tier3(self):
        """cmd >| contains | which triggers pipe detection at base level.
        Either way, result is Tier 3+ and DENY."""
        c = classify("Bash", {"command": "cmd >| /tmp/file"})
        assert c["confidence_tier"] >= TIER_OPAQUE
        e = evaluate(c)
        assert e["policy_decision"] == "DENY"

    def test_input_redirect_tier3(self):
        """cmd < /etc/passwd — unknown command is already Tier 3.
        Redirection opacity floor would also catch it if base tier were lower."""
        c = classify("Bash", {"command": "cmd < /etc/passwd"})
        assert c["confidence_tier"] >= TIER_OPAQUE
        e = evaluate(c)
        assert e["policy_decision"] == "DENY"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
