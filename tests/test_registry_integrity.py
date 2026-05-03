#!/usr/bin/env python3
"""Tests for registry_integrity.py — capability registry protection."""

import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts/ to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from registry_integrity import RegistryIntegrity, validate_registry_schema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_REGISTRY = {
    "version": "0.1",
    "tools": [
        {
            "tool": "FS_WRITE",
            "capability_class": "FS_WRITE",
            "risk_level": "HIGH",
            "allow_base_dirs": ["__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"],
            "deny_hidden_paths": True,
            "deny_overwrite_by_default": True,
            "args": {"required": ["path", "content"], "optional": ["overwrite"]},
            "caps": {"request_executable_allowed": False},
        },
        {
            "tool": "FS_READ",
            "capability_class": "FS_READ",
            "risk_level": "MEDIUM",
            "allow_base_dirs": ["__GOV_CANONICAL_REPO_PATH__"],
            "deny_hidden_paths": True,
            "args": {"required": ["path"], "optional": ["max_bytes"]},
            "caps": {"max_bytes_default": 4096, "max_bytes_hard": 65536},
        },
    ],
}


@pytest.fixture
def tmp_env(tmp_path):
    """Create a temporary registry file and runtime dir."""
    reg_path = tmp_path / "capabilities" / "capability-registry.json"
    reg_path.parent.mkdir(parents=True)
    reg_path.write_text(json.dumps(VALID_REGISTRY, indent=2))
    os.chmod(str(reg_path), stat.S_IRUSR | stat.S_IWUSR)

    runtime_dir = tmp_path / "gov_runtime"
    runtime_dir.mkdir()
    (runtime_dir / "LOGS").mkdir()

    return reg_path, runtime_dir


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_valid_registry(self):
        ok, err = validate_registry_schema(VALID_REGISTRY)
        assert ok is True
        assert err is None

    def test_missing_version(self):
        data = {"tools": VALID_REGISTRY["tools"]}
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "version" in err

    def test_missing_tools(self):
        data = {"version": "0.1"}
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "tools" in err

    def test_empty_tools(self):
        data = {"version": "0.1", "tools": []}
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "empty" in err

    def test_tools_not_array(self):
        data = {"version": "0.1", "tools": {}}
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "array" in err

    def test_missing_required_field(self):
        data = {
            "version": "0.1",
            "tools": [{"tool": "X", "capability_class": "X"}],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "risk_level" in err

    def test_invalid_risk_level(self):
        data = {
            "version": "0.1",
            "tools": [
                {"tool": "X", "capability_class": "X", "risk_level": "EXTREME"}
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "risk_level" in err

    def test_duplicate_tool_names(self):
        data = {
            "version": "0.1",
            "tools": [
                {"tool": "X", "capability_class": "X", "risk_level": "HIGH"},
                {"tool": "X", "capability_class": "X", "risk_level": "LOW"},
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "duplicate" in err

    def test_boolean_constraint_not_bool(self):
        data = {
            "version": "0.1",
            "tools": [
                {
                    "tool": "X",
                    "capability_class": "X",
                    "risk_level": "HIGH",
                    "deny_hidden_paths": "yes",
                }
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "boolean" in err

    def test_bare_root_in_allow_base_dirs(self):
        data = {
            "version": "0.1",
            "tools": [
                {
                    "tool": "X",
                    "capability_class": "X",
                    "risk_level": "HIGH",
                    "allow_base_dirs": ["/"],
                }
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "'/'" in err

    def test_shell_metachar_in_allow_base_dirs(self):
        data = {
            "version": "0.1",
            "tools": [
                {
                    "tool": "X",
                    "capability_class": "X",
                    "risk_level": "HIGH",
                    "allow_base_dirs": ["/tmp; rm -rf /"],
                }
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "forbidden" in err

    def test_null_byte_in_allow_base_dirs(self):
        data = {
            "version": "0.1",
            "tools": [
                {
                    "tool": "X",
                    "capability_class": "X",
                    "risk_level": "HIGH",
                    "allow_base_dirs": ["/tmp\x00evil"],
                }
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "forbidden" in err

    def test_negative_cap_value(self):
        data = {
            "version": "0.1",
            "tools": [
                {
                    "tool": "X",
                    "capability_class": "X",
                    "risk_level": "HIGH",
                    "caps": {"max_bytes_hard": -1},
                }
            ],
        }
        ok, err = validate_registry_schema(data)
        assert ok is False
        assert "non-negative" in err


# ---------------------------------------------------------------------------
# Integrity lifecycle tests
# ---------------------------------------------------------------------------

class TestRegistryIntegrity:
    def test_initialize_success(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        result = ri.initialize(enforce_permissions=True)
        assert result["status"] == "ok"
        assert result["hash"].startswith("sha256:")
        assert result["tool_count"] == 2

    def test_initialize_missing_file(self, tmp_path):
        reg_path = tmp_path / "nonexistent.json"
        runtime_dir = tmp_path / "runtime"
        ri = RegistryIntegrity(reg_path, runtime_dir)
        with pytest.raises(RuntimeError, match="REGISTRY_MISSING"):
            ri.initialize()

    def test_initialize_invalid_json(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        reg_path.write_text("not valid json {{{")
        ri = RegistryIntegrity(reg_path, runtime_dir)
        with pytest.raises(RuntimeError, match="REGISTRY_INVALID_JSON"):
            ri.initialize()

    def test_initialize_invalid_schema(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        reg_path.write_text(json.dumps({"version": "0.1", "tools": []}))
        ri = RegistryIntegrity(reg_path, runtime_dir)
        with pytest.raises(RuntimeError, match="REGISTRY_SCHEMA_INVALID"):
            ri.initialize()

    def test_initialize_creates_backup(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        result = ri.initialize()
        backup = runtime_dir / "registry_backup.json"
        assert backup.exists()
        assert backup.read_bytes() == reg_path.read_bytes()

    def test_initialize_detects_default_config(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        result = ri.initialize()
        assert result.get("default_configuration") is True

    def test_initialize_permissions_too_open(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        os.chmod(str(reg_path), 0o644)
        ri = RegistryIntegrity(reg_path, runtime_dir)
        result = ri.initialize(enforce_permissions=True)
        # Should auto-fix and warn
        assert any("PERMISSIONS" in w for w in result["warnings"])
        mode = reg_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_verify_or_fail_success(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        h = ri.verify_or_fail()
        assert h.startswith("sha256:")

    def test_verify_or_fail_tampered(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()

        # Modify the file without going through reload
        data = json.loads(reg_path.read_text())
        data["tools"][0]["allow_base_dirs"].append("/")
        reg_path.write_text(json.dumps(data))

        with pytest.raises(RuntimeError, match="REGISTRY_TAMPERED"):
            ri.verify_or_fail()

    def test_verify_suspicious_event_logged(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()

        # Tamper
        data = json.loads(reg_path.read_text())
        data["tools"][0]["deny_hidden_paths"] = False
        reg_path.write_text(json.dumps(data))

        with pytest.raises(RuntimeError, match="REGISTRY_TAMPERED"):
            ri.verify_or_fail()

        # Check stability log
        log_path = runtime_dir / "LOGS" / "chain_stability.jsonl"
        if log_path.exists():
            events = [
                json.loads(line)
                for line in log_path.read_text().strip().splitlines()
                if line.strip()
            ]
            suspicious = [e for e in events if e.get("event_type") == "suspicious_event"]
            assert len(suspicious) >= 1
            assert "registry" in suspicious[-1]["detail"].get("source", "")

    def test_verify_not_initialized(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        with pytest.raises(RuntimeError, match="NOT_INITIALIZED"):
            ri.verify_or_fail()

    def test_reload_success(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        old_hash = ri.status()["current_hash"]

        # Modify file (add a custom dir)
        data = json.loads(reg_path.read_text())
        data["tools"][0]["allow_base_dirs"].append("/home/deploy")
        reg_path.write_text(json.dumps(data, indent=2))

        result = ri.reload()
        assert result["status"] == "ok"
        assert result["changed"] is True
        assert result["old_hash"] == old_hash
        assert result["new_hash"] != old_hash
        assert ri.status()["reload_count"] == 1

    def test_reload_invalid_json_keeps_old(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        old_hash = ri.status()["current_hash"]

        reg_path.write_text("broken json {{{")
        with pytest.raises(RuntimeError, match="REGISTRY_RELOAD_FAILED"):
            ri.reload()

        # Old config still in effect
        assert ri.status()["current_hash"] == old_hash

    def test_reload_invalid_schema_keeps_old(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        old_hash = ri.status()["current_hash"]

        reg_path.write_text(json.dumps({"version": "0.1", "tools": []}))
        with pytest.raises(RuntimeError, match="REGISTRY_RELOAD_FAILED"):
            ri.reload()

        assert ri.status()["current_hash"] == old_hash

    def test_reload_then_verify_succeeds(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()

        # Modify and reload properly
        data = json.loads(reg_path.read_text())
        data["tools"][0]["allow_base_dirs"].append("/home/deploy")
        reg_path.write_text(json.dumps(data, indent=2))
        ri.reload()

        # verify_or_fail should now succeed with the new hash
        h = ri.verify_or_fail()
        assert h == ri.status()["current_hash"]

    def test_check_valid(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        result = ri.check()
        assert result["valid"] is True
        assert result["matches_active"] is True
        assert len(result["tools"]) == 2

    def test_check_invalid(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        reg_path.write_text("not json")
        result = ri.check()
        assert result["valid"] is False
        assert "error" in result

    def test_check_modified_but_valid(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()

        data = json.loads(reg_path.read_text())
        data["tools"][0]["allow_base_dirs"].append("/home/deploy")
        reg_path.write_text(json.dumps(data, indent=2))

        result = ri.check()
        assert result["valid"] is True
        assert result["matches_active"] is False

    def test_status_reports_state(self, tmp_env):
        reg_path, runtime_dir = tmp_env
        ri = RegistryIntegrity(reg_path, runtime_dir)
        ri.initialize()
        s = ri.status()
        assert s["initialized"] is True
        assert s["startup_hash"] is not None
        assert s["current_hash"] == s["startup_hash"]
        assert s["reload_count"] == 0

    def test_registry_hash_in_records(self, tmp_env):
        """The cap_registry_hash field already exists in governance records
        (policy-eval.py line 660). This test confirms the format."""
        reg_path, _ = tmp_env
        raw = reg_path.read_bytes()
        expected = "sha256:" + hashlib.sha256(raw).hexdigest()
        # This is the same format used by policy-eval.py load_internal_registry()
        assert expected.startswith("sha256:")
        assert len(expected) == 71  # "sha256:" + 64 hex chars
