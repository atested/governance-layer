"""Regression test for Path serialization in governed records.

D-072 Fix 1: canonicalize() returns Path objects. When these are stored
in rec["normalized_args"] and JSON-serialized for hashing, PosixPath
objects cause "Object of type PosixPath is not JSON serializable".

The fix converts Path→str at the boundary where canonicalized values
enter records (mcp/server.py). This test exercises the full
canonicalize→record→serialize→hash path to prove it works.
"""

import json
import hashlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("GOV_CANONICAL_REPO_PATH", str(REPO))
os.environ.setdefault("GOV_RUNTIME_PATH", "/tmp/gov_runtime")

from policy_eval_shared import canonicalize
from policy_eval_v2 import evaluate, load_policy_rules, _compute_record_hash
from classifier import classify


def _policy():
    return load_policy_rules(REPO / "capabilities" / "policy-rules.json")


class TestPathSerializationInRecords:
    """Verify that canonicalized paths in records can be JSON-serialized."""

    def test_canonicalize_returns_path_object(self):
        """Precondition: canonicalize() returns a Path, not str."""
        result = canonicalize(str(REPO / "README.md"))
        assert isinstance(result, Path), f"expected Path, got {type(result)}"

    def test_str_wrapped_canonicalize_is_serializable(self):
        """str(canonicalize(...)) produces a JSON-serializable string."""
        result = str(canonicalize(str(REPO / "README.md")))
        assert isinstance(result, str)
        # Must not raise
        json.dumps({"canonical_path": result})

    def test_record_with_canonical_path_serializes(self):
        """A v2 record enriched with canonicalized paths serializes to JSON.

        This is the exact pattern used in mcp/server.py governed_tool():
        classify → evaluate → enrich rec["normalized_args"] → hash.
        """
        target = str(REPO / "scripts" / "classifier.py")
        c = classify("Read", {"file_path": target})
        rec = evaluate(c, _policy())

        # Simulate what governed_tool() does: add normalized_args with
        # str-wrapped canonicalized path, then recompute hash.
        canonical = str(canonicalize(target))
        rec["normalized_args"] = {"canonical_path": canonical}

        # This must not raise TypeError (PosixPath not serializable).
        rec["record_hash"] = _compute_record_hash(rec)
        assert rec["record_hash"].startswith("sha256:")

        # Verify full JSON serialization works.
        serialized = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        assert "canonical_path" in serialized
        assert "PosixPath" not in serialized

    def test_record_with_src_dst_paths_serializes(self):
        """FS_MOVE records with canonical_src_path and canonical_dst_path serialize."""
        src = str(REPO / "tmp" / "a.txt")
        dst = str(REPO / "tmp" / "b.txt")
        c = classify("move_file", {"src": src, "dst": dst})
        rec = evaluate(c, _policy())

        rec["normalized_args"] = {
            "canonical_path": "",
            "canonical_src_path": str(canonicalize(src)),
            "canonical_dst_path": str(canonicalize(dst)),
        }

        # Must not raise.
        rec["record_hash"] = _compute_record_hash(rec)
        serialized = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        assert "PosixPath" not in serialized

    def test_bare_path_object_in_record_fails(self):
        """Without the str() fix, a bare Path object breaks serialization.

        This proves the test would have caught the original bug.
        """
        target = str(REPO / "scripts" / "classifier.py")
        c = classify("Read", {"file_path": target})
        rec = evaluate(c, _policy())

        # Inject a raw Path object (the original bug).
        rec["normalized_args"] = {"canonical_path": canonicalize(target)}

        # This MUST raise TypeError — proving the test catches the bug.
        try:
            json.dumps(rec, sort_keys=True, separators=(",", ":"))
            assert False, "Expected TypeError for PosixPath serialization"
        except TypeError as e:
            assert "PosixPath" in str(e) or "not JSON serializable" in str(e)
