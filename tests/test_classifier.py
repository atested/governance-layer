"""Tests for the GovMCP v2 evidence-based classifier."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classifier import (
    classify,
    ACTION_READ, ACTION_WRITE, ACTION_DELETE, ACTION_EXECUTE,
    ACTION_NETWORK, ACTION_MOVE, ACTION_LIST, ACTION_CREATE_DIR,
    ACTION_UNKNOWN,
    SCOPE_LOCAL, SCOPE_REPOSITORY, SCOPE_SYSTEM, SCOPE_REMOTE,
    SCOPE_PRIVILEGED,
    TIER_DIRECT, TIER_INFERRED, TIER_OPAQUE, TIER_UNINSPECTABLE,
)


# ---------------------------------------------------------------------------
# Tier 1 — Directly observable (file path operations)
# ---------------------------------------------------------------------------

class TestTier1FileRead:
    def test_read_with_file_path(self):
        r = classify("Read", {"file_path": "/tmp/data.txt"})
        assert r["action_type"] == ACTION_READ
        assert r["confidence_tier"] == TIER_DIRECT
        assert "/tmp/data.txt" in r["targets"]

    def test_read_with_path_param(self):
        r = classify("fs_read", {"path": "/home/user/file.py"})
        assert r["action_type"] == ACTION_READ
        assert r["confidence_tier"] == TIER_DIRECT

    def test_read_various_tool_names(self):
        for name in ("Read", "read_file", "get_contents", "fetch_data", "cat_file", "load_config"):
            r = classify(name, {"file_path": "/tmp/f.txt"})
            assert r["action_type"] == ACTION_READ, f"Failed for tool: {name}"

    def test_camel_case_tool_name(self):
        r = classify("ReadFile", {"file_path": "/tmp/f.txt"})
        assert r["action_type"] == ACTION_READ


class TestTier1FileWrite:
    def test_write_with_file_path(self):
        r = classify("Write", {"file_path": "/tmp/out.txt", "content": "hello"})
        assert r["action_type"] == ACTION_WRITE
        assert r["confidence_tier"] == TIER_DIRECT
        assert "/tmp/out.txt" in r["targets"]

    def test_edit_is_write(self):
        r = classify("Edit", {"file_path": "/tmp/f.py", "old_string": "a", "new_string": "b"})
        assert r["action_type"] == ACTION_WRITE

    def test_write_various_names(self):
        for name in ("Write", "write_file", "save_file", "create_file", "store_data"):
            r = classify(name, {"file_path": "/tmp/f.txt", "content": "x"})
            assert r["action_type"] == ACTION_WRITE, f"Failed for tool: {name}"


class TestTier1FileDelete:
    def test_delete_with_file_path(self):
        r = classify("delete_file", {"file_path": "/tmp/old.txt"})
        assert r["action_type"] == ACTION_DELETE
        assert r["confidence_tier"] == TIER_DIRECT

    def test_remove_tool(self):
        r = classify("rm_file", {"path": "/tmp/junk.log"})
        assert r["action_type"] == ACTION_DELETE


class TestTier1FileMove:
    def test_move_file(self):
        r = classify("move_file", {"src": "/tmp/a.txt", "dst": "/tmp/b.txt"})
        assert r["action_type"] == ACTION_MOVE
        assert r["confidence_tier"] == TIER_DIRECT
        assert len(r["targets"]) == 2


class TestTier1ListSearch:
    def test_list_directory(self):
        r = classify("Glob", {"pattern": "*.py", "path": "/tmp"})
        assert r["action_type"] == ACTION_LIST
        assert r["confidence_tier"] == TIER_DIRECT

    def test_grep_search(self):
        r = classify("Grep", {"pattern": "TODO", "path": "/src"})
        assert r["action_type"] == ACTION_READ  # Grep reads files by content

    def test_ls_tool(self):
        r = classify("list_files", {"path": "/tmp"})
        assert r["action_type"] == ACTION_LIST


class TestTier1Mkdir:
    def test_mkdir(self):
        r = classify("mkdir", {"path": "/tmp/new_dir"})
        assert r["action_type"] == ACTION_CREATE_DIR
        assert r["confidence_tier"] == TIER_DIRECT


class TestTier1Network:
    def test_url_in_params(self):
        r = classify("WebFetch", {"url": "https://api.example.com/data"})
        assert r["action_type"] == ACTION_NETWORK
        assert r["scope"] == SCOPE_REMOTE
        assert "https://api.example.com/data" in r["targets"]


# ---------------------------------------------------------------------------
# Tier 1 — Scope detection
# ---------------------------------------------------------------------------

class TestScopeDetection:
    def test_sensitive_ssh_path(self):
        r = classify("Read", {"file_path": "~/.ssh/id_rsa"})
        assert r["scope"] == SCOPE_PRIVILEGED

    def test_sensitive_env_file(self):
        r = classify("Read", {"file_path": "/app/.env"})
        assert r["scope"] == SCOPE_PRIVILEGED

    def test_sensitive_etc(self):
        r = classify("Write", {"file_path": "/etc/hosts", "content": "x"})
        assert r["scope"] == SCOPE_PRIVILEGED

    def test_system_path(self):
        r = classify("Read", {"file_path": "/usr/local/bin/tool"})
        assert r["scope"] == SCOPE_SYSTEM

    def test_normal_path(self):
        r = classify("Read", {"file_path": "/home/user/project/main.py"})
        assert r["scope"] == SCOPE_LOCAL


# ---------------------------------------------------------------------------
# Tier 2 — Inferred from commands
# ---------------------------------------------------------------------------

class TestTier2Commands:
    def test_git_push(self):
        r = classify("Bash", {"command": "git push origin main"})
        assert r["action_type"] == ACTION_NETWORK
        assert r["scope"] == SCOPE_REMOTE
        assert r["confidence_tier"] == TIER_INFERRED

    def test_git_status(self):
        r = classify("Bash", {"command": "git status"})
        assert r["action_type"] == ACTION_READ
        assert r["scope"] == SCOPE_REPOSITORY
        assert r["confidence_tier"] == TIER_INFERRED

    def test_git_commit(self):
        r = classify("Bash", {"command": "git commit -m 'fix bug'"})
        assert r["action_type"] == ACTION_WRITE
        assert r["scope"] == SCOPE_REPOSITORY

    def test_curl_command(self):
        r = classify("Bash", {"command": "curl https://example.com/api"})
        assert r["action_type"] == ACTION_NETWORK
        # URL is directly observable in parameters → Tier 1
        assert r["confidence_tier"] == TIER_DIRECT

    def test_rm_command(self):
        r = classify("Bash", {"command": "rm -rf /tmp/cache"})
        assert r["action_type"] == ACTION_DELETE
        assert r["confidence_tier"] == TIER_INFERRED
        assert "/tmp/cache" in r["targets"]

    def test_npm_install(self):
        r = classify("Bash", {"command": "npm install express"})
        assert r["action_type"] == ACTION_EXECUTE
        assert r["scope"] == SCOPE_REMOTE
        assert r["confidence_tier"] == TIER_INFERRED

    def test_pytest(self):
        r = classify("Bash", {"command": "pytest tests/ -v"})
        assert r["action_type"] == ACTION_EXECUTE
        assert r["scope"] == SCOPE_LOCAL
        assert r["confidence_tier"] == TIER_INFERRED

    def test_make_build(self):
        r = classify("Bash", {"command": "make build"})
        assert r["action_type"] == ACTION_EXECUTE
        assert r["confidence_tier"] == TIER_INFERRED

    def test_docker_run(self):
        r = classify("Bash", {"command": "docker run -it ubuntu bash"})
        assert r["action_type"] == ACTION_EXECUTE
        assert r["scope"] == SCOPE_SYSTEM
        assert r["confidence_tier"] == TIER_INFERRED

    def test_redirect_is_write(self):
        r = classify("Bash", {"command": "echo hello > /tmp/out.txt"})
        assert r["action_type"] == ACTION_WRITE
        assert r["confidence_tier"] == TIER_INFERRED


# ---------------------------------------------------------------------------
# Tier 3 — Opaque execution
# ---------------------------------------------------------------------------

class TestTier3Opaque:
    def test_python_script(self):
        r = classify("Bash", {"command": "python deploy.sh"})
        assert r["confidence_tier"] == TIER_OPAQUE
        assert r["action_type"] == ACTION_EXECUTE

    def test_bash_script(self):
        r = classify("Bash", {"command": "bash scripts/setup.sh"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_node_script(self):
        r = classify("Bash", {"command": "node build.js"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_python_inline(self):
        r = classify("Bash", {"command": "python -c 'import os; os.system(\"rm -rf /\")'"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_pipe_chain(self):
        r = classify("Bash", {"command": "cat /etc/passwd | grep root | awk '{print $1}'"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_command_substitution(self):
        r = classify("Bash", {"command": "echo $(whoami)"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_unknown_binary(self):
        r = classify("Bash", {"command": "projectctl deploy --env=prod"})
        assert r["confidence_tier"] == TIER_OPAQUE

    def test_no_recognizable_evidence(self):
        r = classify("mystery_tool", {"config": {"nested": True}})
        assert r["confidence_tier"] == TIER_OPAQUE
        assert r["action_type"] == ACTION_UNKNOWN


# ---------------------------------------------------------------------------
# Tier 4 — Uninspectable
# ---------------------------------------------------------------------------

class TestTier4Uninspectable:
    def test_base64_payload(self):
        encoded = "cHl0aG9uIC1jICdpbXBvcnQgb3M7IG9zLnN5c3RlbSgicm0gLXJmIC8iKSc="
        r = classify("Bash", {"command": encoded})
        assert r["confidence_tier"] == TIER_UNINSPECTABLE

    def test_long_hex_blob(self):
        hex_blob = "a" * 64
        r = classify("some_tool", {"data": hex_blob})
        assert r["confidence_tier"] == TIER_UNINSPECTABLE

    def test_normal_short_base64_not_flagged(self):
        # Short strings should not trigger Tier 4
        r = classify("Read", {"file_path": "/tmp/data.txt"})
        assert r["confidence_tier"] != TIER_UNINSPECTABLE


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_all_fields_present(self):
        r = classify("Read", {"file_path": "/tmp/test.txt"})
        assert "action_type" in r
        assert "targets" in r
        assert "scope" in r
        assert "confidence_tier" in r
        assert "evidence" in r
        assert "original_tool" in r
        assert "source" in r["evidence"]
        assert "details" in r["evidence"]

    def test_original_tool_preserved(self):
        r = classify("MyCustomReadTool", {"file_path": "/tmp/f.txt"})
        assert r["original_tool"] == "MyCustomReadTool"

    def test_targets_is_list(self):
        r = classify("Read", {"file_path": "/tmp/f.txt"})
        assert isinstance(r["targets"], list)

    def test_empty_args(self):
        r = classify("unknown", {})
        assert r["confidence_tier"] == TIER_OPAQUE
        assert r["action_type"] == ACTION_UNKNOWN
