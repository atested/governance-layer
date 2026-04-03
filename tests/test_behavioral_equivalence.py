#!/usr/bin/env python3
"""
test_behavioral_equivalence.py — Behavioral equivalence validation for v1→v2 cutover.

Replays historical v1 chain records through the v2 classifier and evaluator.
Operations that were ALLOW'd in v1 must get ALLOW in v2.
Operations that were DENY'd in v1 must get DENY in v2.

Known divergences are documented and tested separately.
"""

import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classifier import classify
from policy_eval_v2 import evaluate, load_policy_rules

CHAIN_PATH = REPO / "gov_runtime" / "LOGS" / "decision-chain.jsonl"
_REPO_STR = str(REPO)


def _load_v1_action_records() -> list[dict]:
    """Load v1 pass_decision records from the chain file."""
    records = []
    if not CHAIN_PATH.exists():
        return records
    with open(CHAIN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") == "pass_decision":
                records.append(rec)
    return records


def _make_policy_with_base_dirs(base_dirs: list[str]) -> dict:
    """Load policy rules and override base_dirs."""
    policy = load_policy_rules()
    policy["base_dirs"] = base_dirs
    return policy


def _reconstruct_args(v1_record: dict) -> dict:
    """Reconstruct tool args from a v1 chain record for v2 classification.

    The v1 record has normalized_args with canonical_path. We reconstruct
    args that the classifier can interpret (it looks for 'path', 'file_path',
    etc.).
    """
    norm = v1_record.get("normalized_args", {})
    tool = v1_record.get("tool", "")

    # FS_* tools: use canonical_path as 'path'
    if tool.startswith("FS_"):
        args = {"path": norm.get("canonical_path", "")}
        # Preserve write-specific args
        if tool == "FS_WRITE":
            if norm.get("overwrite"):
                args["overwrite"] = norm["overwrite"]
            if norm.get("request_executable"):
                args["request_executable"] = norm["request_executable"]
        return args

    # MSG_SEND: no file path — classifier will see opaque
    if tool == "MSG_SEND":
        return {}

    # Fallback: return raw args minus internal fields
    return {k: v for k, v in norm.items() if k not in ("canonical_path", "max_bytes_hard")}


def _extract_base_dirs(v1_record: dict) -> list[str]:
    """Extract base_dirs from a v1 record's policy_inputs."""
    return v1_record.get("policy_inputs", {}).get("allow_base_dirs", [_REPO_STR])


class TestBehavioralEquivalence(unittest.TestCase):
    """Replay v1 chain records through v2 pipeline and validate decision parity."""

    @classmethod
    def setUpClass(cls):
        cls.v1_records = _load_v1_action_records()
        if not cls.v1_records:
            raise unittest.SkipTest("No v1 chain records found")

    def test_chain_has_action_records(self):
        """Chain contains v1 action records to validate against."""
        self.assertGreater(len(self.v1_records), 0)

    def test_all_fs_decisions_match(self):
        """Every FS_* v1 decision matches when replayed through v2."""
        fs_records = [r for r in self.v1_records if r["tool"].startswith("FS_")]
        self.assertGreater(len(fs_records), 0, "No FS_* records to validate")

        mismatches = []
        for rec in fs_records:
            tool = rec["tool"]
            v1_decision = rec["policy_decision"]
            base_dirs = _extract_base_dirs(rec)
            args = _reconstruct_args(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify(tool, args)
            v2_record = evaluate(classification, policy)
            v2_decision = v2_record["policy_decision"]

            if v1_decision != v2_decision:
                mismatches.append({
                    "tool": tool,
                    "path": args.get("path", ""),
                    "v1": v1_decision,
                    "v2": v2_decision,
                    "v2_rule": v2_record.get("matched_rule", ""),
                    "v2_action_type": classification["action_type"],
                    "v2_tier": classification["confidence_tier"],
                })

        if mismatches:
            detail = json.dumps(mismatches, indent=2)
            self.fail(f"{len(mismatches)} decision mismatch(es):\n{detail}")

    def test_fs_read_allow_within_base_dirs(self):
        """FS_READ within base dirs: v1 ALLOW → v2 ALLOW."""
        allows = [
            r for r in self.v1_records
            if r["tool"] == "FS_READ" and r["policy_decision"] == "ALLOW"
        ]
        self.assertGreater(len(allows), 0)

        for rec in allows:
            args = _reconstruct_args(rec)
            base_dirs = _extract_base_dirs(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify("FS_READ", args)
            self.assertEqual(classification["action_type"], "read")
            self.assertEqual(classification["confidence_tier"], 1)

            v2_record = evaluate(classification, policy)
            self.assertEqual(
                v2_record["policy_decision"], "ALLOW",
                f"FS_READ at {args.get('path')} should be ALLOW but got DENY "
                f"(rule: {v2_record.get('matched_rule')})"
            )

    def test_fs_read_deny_outside_base_dirs(self):
        """FS_READ outside base dirs: v1 DENY → v2 DENY."""
        denies = [
            r for r in self.v1_records
            if r["tool"] == "FS_READ" and r["policy_decision"] == "DENY"
        ]
        if not denies:
            self.skipTest("No FS_READ DENY records in chain")

        for rec in denies:
            args = _reconstruct_args(rec)
            base_dirs = _extract_base_dirs(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify("FS_READ", args)
            v2_record = evaluate(classification, policy)
            self.assertEqual(
                v2_record["policy_decision"], "DENY",
                f"FS_READ at {args.get('path')} should be DENY but got ALLOW"
            )

    def test_fs_write_allow_within_base_dirs(self):
        """FS_WRITE within base dirs: v1 ALLOW → v2 ALLOW."""
        allows = [
            r for r in self.v1_records
            if r["tool"] == "FS_WRITE" and r["policy_decision"] == "ALLOW"
        ]
        if not allows:
            self.skipTest("No FS_WRITE ALLOW records in chain")

        for rec in allows:
            args = _reconstruct_args(rec)
            base_dirs = _extract_base_dirs(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify("FS_WRITE", args)
            self.assertEqual(classification["action_type"], "write")

            v2_record = evaluate(classification, policy)
            self.assertEqual(
                v2_record["policy_decision"], "ALLOW",
                f"FS_WRITE at {args.get('path')} should be ALLOW"
            )

    def test_fs_list_allow_within_base_dirs(self):
        """FS_LIST within base dirs: v1 ALLOW → v2 ALLOW."""
        allows = [
            r for r in self.v1_records
            if r["tool"] == "FS_LIST" and r["policy_decision"] == "ALLOW"
        ]
        if not allows:
            self.skipTest("No FS_LIST ALLOW records in chain")

        for rec in allows:
            args = _reconstruct_args(rec)
            base_dirs = _extract_base_dirs(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify("FS_LIST", args)
            self.assertEqual(classification["action_type"], "list")

            v2_record = evaluate(classification, policy)
            self.assertEqual(
                v2_record["policy_decision"], "ALLOW",
                f"FS_LIST at {args.get('path')} should be ALLOW"
            )

    def test_classification_mapping_correctness(self):
        """v1 tool names map to correct v2 action types."""
        expected = {
            "FS_READ": "read",
            "FS_WRITE": "write",
            "FS_LIST": "list",
            "FS_DELETE": "delete",
            "FS_MOVE": "move",
            "FS_MKDIR": "create_directory",
        }
        for v1_tool, expected_action in expected.items():
            # Classify with a path arg so we get Tier 1
            classification = classify(v1_tool, {"path": "/tmp/test"})
            self.assertEqual(
                classification["action_type"], expected_action,
                f"{v1_tool} should map to {expected_action} but got {classification['action_type']}"
            )

    def test_msg_send_known_divergence(self):
        """MSG_SEND is a known divergence: v1 uses opaque path, v2 classifies as opaque.

        Both produce DENY but for different reasons. In v1, MSG_SEND is denied
        by RC-MSG-UNKNOWN-SURFACE-BINDING (messaging-specific check). In v2,
        MSG_SEND with no recognizable parameters is classified as Tier 3 opaque
        and denied by the tier3-approval-required rule.

        The key invariant holds: both v1 and v2 DENY this operation.
        """
        msg_records = [r for r in self.v1_records if r["tool"] == "MSG_SEND"]
        if not msg_records:
            self.skipTest("No MSG_SEND records in chain")

        for rec in msg_records:
            v1_decision = rec["policy_decision"]
            args = _reconstruct_args(rec)
            base_dirs = _extract_base_dirs(rec)
            policy = _make_policy_with_base_dirs(base_dirs)

            classification = classify("MSG_SEND", args)
            # MSG_SEND with no file paths → opaque
            self.assertIn(classification["confidence_tier"], [3, 4])

            v2_record = evaluate(classification, policy)
            # Both v1 and v2 deny this — divergence is in the reason, not the decision
            if v1_decision == "DENY":
                self.assertEqual(v2_record["policy_decision"], "DENY")


class TestSyntheticEquivalence(unittest.TestCase):
    """Synthetic test cases that cover scenarios not in the chain but important for parity."""

    def setUp(self):
        self.policy = _make_policy_with_base_dirs([_REPO_STR])

    def test_read_sensitive_path_denied(self):
        """Read of /etc/shadow → DENY (sensitive path)."""
        classification = classify("FS_READ", {"path": "/etc/shadow"})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "DENY")

    def test_read_home_ssh_denied(self):
        """Read of ~/.ssh/id_rsa → DENY (sensitive path)."""
        classification = classify("FS_READ", {"path": os.path.expanduser("~/.ssh/id_rsa")})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "DENY")

    def test_write_within_repo_allowed(self):
        """Write within repo → ALLOW."""
        path = os.path.join(_REPO_STR, "test_output.txt")
        classification = classify("FS_WRITE", {"path": path})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "ALLOW")

    def test_write_outside_repo_denied(self):
        """Write outside repo → DENY."""
        classification = classify("FS_WRITE", {"path": "/tmp/outside.txt"})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "DENY")

    def test_delete_within_repo_allowed(self):
        """Delete within repo → ALLOW."""
        path = os.path.join(_REPO_STR, "temp_file.txt")
        classification = classify("FS_DELETE", {"path": path})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "ALLOW")

    def test_delete_outside_repo_denied(self):
        """Delete outside repo → DENY."""
        classification = classify("FS_DELETE", {"path": "/usr/bin/something"})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "DENY")

    def test_list_within_repo_allowed(self):
        """List within repo → ALLOW."""
        classification = classify("FS_LIST", {"path": _REPO_STR})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "ALLOW")

    def test_hidden_path_write_denied(self):
        """Write to hidden path within repo → DENY."""
        path = os.path.join(_REPO_STR, ".secret", "file.txt")
        classification = classify("FS_WRITE", {"path": path})
        v2_record = evaluate(classification, self.policy)
        self.assertEqual(v2_record["policy_decision"], "DENY")

    def test_v2_record_format(self):
        """v2 decision records have correct structure."""
        path = os.path.join(_REPO_STR, "README.md")
        classification = classify("FS_READ", {"path": path})
        record = evaluate(classification, self.policy)

        self.assertEqual(record["record_version"], "2.0")
        self.assertEqual(record["record_type"], "mediated_decision")
        self.assertIn("classification", record)
        self.assertIn("evidence", record)
        self.assertIn("record_hash", record)
        self.assertIn("prev_record_hash", record)
        self.assertIn("matched_rule", record)
        self.assertIn("policy_decision", record)
        self.assertIn("original_tool", record)


if __name__ == "__main__":
    unittest.main()
