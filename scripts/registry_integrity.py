#!/usr/bin/env python3
"""
registry_integrity.py — Integrity protection for capability-registry.json.

This file controls what every governed tool is allowed to do. It defines
allowed directories, per-tool constraints, and hard caps. A modified registry
could silently expand the governance boundary, remove constraints, or corrupt
the entire governance surface.

This module provides:
  1. Startup hash verification and storage
  2. Per-call hash verification (fail closed on mismatch)
  3. File permission enforcement (0600)
  4. Schema validation
  5. Backup on startup
  6. Tamper detection (unauthorized modification → SUSPICIOUS event)
  7. Governed reload with validation
"""

import hashlib
import json
import os
import shutil
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

# Required fields for each tool entry in the registry
REQUIRED_TOOL_FIELDS = {"tool", "capability_class", "risk_level"}
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
BOOLEAN_CONSTRAINT_FIELDS = {
    "deny_hidden_paths", "deny_traversal", "deny_overwrite_by_default",
    "deny_executable_outputs",
}
# Characters that must never appear in allow_base_dirs entries
FORBIDDEN_PATH_CHARS = frozenset("\x00|;&$`\\\"'<>(){}!")


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    """Compute sha256:hex of a file's raw bytes."""
    raw = path.read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_registry_schema(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate capability-registry.json against the expected schema.

    Returns (True, None) on success or (False, error_message) on failure.
    """
    if not isinstance(data, dict):
        return False, "Registry must be a JSON object"

    if "version" not in data:
        return False, "Missing required field: version"

    if "tools" not in data:
        return False, "Missing required field: tools"

    tools = data["tools"]
    if not isinstance(tools, list):
        return False, "tools must be an array"

    if len(tools) == 0:
        return False, "tools array must not be empty"

    seen_tool_names = set()
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            return False, f"tools[{i}]: must be a JSON object"

        # Required fields
        for field in REQUIRED_TOOL_FIELDS:
            if field not in tool:
                return False, f"tools[{i}]: missing required field '{field}'"

        tool_name = tool["tool"]
        if not isinstance(tool_name, str) or not tool_name.strip():
            return False, f"tools[{i}]: 'tool' must be a non-empty string"

        if tool_name in seen_tool_names:
            return False, f"tools[{i}]: duplicate tool name '{tool_name}'"
        seen_tool_names.add(tool_name)

        # Risk level
        if tool["risk_level"] not in VALID_RISK_LEVELS:
            return False, f"tools[{i}] ({tool_name}): invalid risk_level '{tool['risk_level']}'"

        # Boolean constraints
        for field in BOOLEAN_CONSTRAINT_FIELDS:
            if field in tool and not isinstance(tool[field], bool):
                return False, f"tools[{i}] ({tool_name}): '{field}' must be a boolean"

        # allow_base_dirs
        if "allow_base_dirs" in tool:
            abd = tool["allow_base_dirs"]
            if not isinstance(abd, list):
                return False, f"tools[{i}] ({tool_name}): allow_base_dirs must be an array"
            for j, entry in enumerate(abd):
                if not isinstance(entry, str):
                    return False, f"tools[{i}] ({tool_name}): allow_base_dirs[{j}] must be a string"
                if not entry.strip():
                    return False, f"tools[{i}] ({tool_name}): allow_base_dirs[{j}] must not be empty"
                # Forbid bare root
                if entry == "/":
                    return False, f"tools[{i}] ({tool_name}): allow_base_dirs[{j}] must not be '/'"
                # Forbid shell metacharacters and null bytes
                for ch in FORBIDDEN_PATH_CHARS:
                    if ch in entry:
                        return False, (
                            f"tools[{i}] ({tool_name}): allow_base_dirs[{j}] "
                            f"contains forbidden character '{ch}'"
                        )

        # Caps validation
        if "caps" in tool:
            caps = tool["caps"]
            if not isinstance(caps, dict):
                return False, f"tools[{i}] ({tool_name}): caps must be a JSON object"
            for cap_key, cap_val in caps.items():
                if isinstance(cap_val, int) and not isinstance(cap_val, bool):
                    if cap_val < 0:
                        return False, (
                            f"tools[{i}] ({tool_name}): caps.{cap_key} "
                            f"must be non-negative (got {cap_val})"
                        )

        # Args validation
        if "args" in tool:
            args = tool["args"]
            if not isinstance(args, dict):
                return False, f"tools[{i}] ({tool_name}): args must be a JSON object"
            for key in ("required", "optional"):
                if key in args and not isinstance(args[key], list):
                    return False, f"tools[{i}] ({tool_name}): args.{key} must be an array"

    return True, None


# ---------------------------------------------------------------------------
# Registry integrity state
# ---------------------------------------------------------------------------

class RegistryIntegrity:
    """Tracks and enforces integrity of the capability registry.

    Thread-safe. One instance per server process.
    """

    def __init__(self, registry_path: Path, runtime_dir: Path):
        self._registry_path = registry_path
        self._runtime_dir = runtime_dir
        self._stability_log_path = runtime_dir / "LOGS" / "chain_stability.jsonl"
        self._backup_path = runtime_dir / "registry_backup.json"
        self._lock = threading.Lock()

        # Set at startup, immutable until reload
        self._startup_hash: Optional[str] = None
        self._current_hash: Optional[str] = None
        self._last_verified: Optional[str] = None
        self._startup_time: Optional[str] = None
        self._reload_count: int = 0

    # -- Startup -------------------------------------------------------

    def initialize(
        self,
        *,
        enforce_permissions: bool = True,
        log_fn=None,
    ) -> Dict[str, Any]:
        """Initialize registry integrity at server startup.

        1. Verify file exists and is readable
        2. Check file permissions
        3. Compute and store hash
        4. Validate schema
        5. Create backup

        Returns status dict. Raises RuntimeError on fatal errors (fail closed).
        """
        result = {
            "registry_path": str(self._registry_path),
            "status": "ok",
            "warnings": [],
        }

        # 1. Verify file exists
        if not self._registry_path.exists():
            raise RuntimeError(
                f"REGISTRY_MISSING: capability-registry.json not found at "
                f"{self._registry_path}. Cannot start governance server."
            )

        if not self._registry_path.is_file():
            raise RuntimeError(
                f"REGISTRY_NOT_FILE: {self._registry_path} is not a regular file."
            )

        # 2. Check file permissions (Unix only)
        try:
            file_stat = self._registry_path.stat()
            mode = file_stat.st_mode & 0o777
            if mode & 0o077:  # group or world bits set
                msg = (
                    f"REGISTRY_PERMISSIONS_TOO_OPEN: {self._registry_path} has mode "
                    f"{oct(mode)}. Expected 0600 or stricter. "
                    f"Other users on this system could read or modify the governance boundary."
                )
                if enforce_permissions:
                    result["warnings"].append(msg)
                    # Auto-fix: tighten to 0600
                    try:
                        os.chmod(str(self._registry_path), stat.S_IRUSR | stat.S_IWUSR)
                        result["warnings"].append(
                            f"Auto-fixed permissions to 0600 on {self._registry_path}"
                        )
                    except OSError as e:
                        raise RuntimeError(
                            f"{msg} Failed to auto-fix: {e}. "
                            f"Fix manually: chmod 600 {self._registry_path}"
                        )
                else:
                    result["warnings"].append(msg + " (enforcement disabled)")
        except OSError:
            pass  # Non-Unix platform — skip permission check

        # 3. Read and hash
        try:
            raw = self._registry_path.read_bytes()
        except OSError as e:
            raise RuntimeError(f"REGISTRY_UNREADABLE: {e}")

        file_hash = _sha256_bytes(raw)

        # 4. Parse and validate schema
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(f"REGISTRY_INVALID_JSON: {e}")

        valid, err = validate_registry_schema(data)
        if not valid:
            raise RuntimeError(f"REGISTRY_SCHEMA_INVALID: {err}")

        # 5. Store hash
        with self._lock:
            self._startup_hash = file_hash
            self._current_hash = file_hash
            self._last_verified = _now_utc_z()
            self._startup_time = _now_utc_z()

        result["hash"] = file_hash
        result["tool_count"] = len(data.get("tools", []))

        # 6. Backup
        try:
            self._runtime_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(self._registry_path), str(self._backup_path))
            result["backup_path"] = str(self._backup_path)
        except OSError as e:
            result["warnings"].append(f"Failed to create backup: {e}")

        # 7. Log startup event
        self._log_stability_event("server_start", {
            "description": "Registry integrity initialized",
            "registry_hash": file_hash,
            "tool_count": len(data.get("tools", [])),
            "permissions_enforced": enforce_permissions,
        })

        # 8. Detect default configuration
        default_dirs_only = all(
            set(t.get("allow_base_dirs", [])) <= {
                "__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"
            }
            for t in data.get("tools", [])
        )
        if default_dirs_only:
            result["default_configuration"] = True
            result["warnings"].append(
                "Atested is using default configuration. Your governed tools are "
                "limited to the project repository directory. To expand scope, edit "
                "capabilities/capability-registry.json — see docs/QUICKSTART.md for guidance."
            )

        return result

    # -- Per-call verification -----------------------------------------

    def verify_or_fail(self) -> str:
        """Verify the registry hasn't been tampered with since startup/reload.

        Returns the current hash if OK.
        Raises RuntimeError if the file has changed (fail closed).
        """
        if self._current_hash is None:
            raise RuntimeError(
                "REGISTRY_NOT_INITIALIZED: Registry integrity was not initialized. "
                "Cannot evaluate governed actions."
            )

        try:
            current_file_hash = _sha256_file(self._registry_path)
        except OSError as e:
            raise RuntimeError(
                f"REGISTRY_UNREADABLE_DURING_VERIFICATION: {e}. "
                f"Refusing to evaluate — fail closed."
            )

        with self._lock:
            self._last_verified = _now_utc_z()

            if current_file_hash != self._current_hash:
                # UNAUTHORIZED MODIFICATION DETECTED
                self._log_stability_event("suspicious_event", {
                    "description": "Registry modified without governed reload",
                    "source": "registry_integrity",
                    "expected_hash": self._current_hash,
                    "actual_hash": current_file_hash,
                    "startup_hash": self._startup_hash,
                    "action": "fail_closed",
                })
                raise RuntimeError(
                    f"REGISTRY_TAMPERED: capability-registry.json has been modified "
                    f"without a governed registry_reload. Expected hash: "
                    f"{self._current_hash}, found: {current_file_hash}. "
                    f"Refusing to evaluate — fail closed. Use the registry_reload "
                    f"tool to apply configuration changes through governance."
                )

            return current_file_hash

    # -- Governed reload -----------------------------------------------

    def reload(self) -> Dict[str, Any]:
        """Reload the registry through a governed process.

        1. Read the new file
        2. Validate JSON
        3. Validate schema
        4. Record the change (old hash → new hash)
        5. Update the stored hash

        Returns status dict. Raises RuntimeError on validation failure (fail closed).
        """
        old_hash = self._current_hash

        # Read new file
        try:
            raw = self._registry_path.read_bytes()
        except OSError as e:
            raise RuntimeError(f"REGISTRY_RELOAD_FAILED: Cannot read file: {e}")

        new_hash = _sha256_bytes(raw)

        # Parse
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(
                f"REGISTRY_RELOAD_FAILED: Invalid JSON: {e}. "
                f"The previous configuration remains in effect."
            )

        # Validate schema
        valid, err = validate_registry_schema(data)
        if not valid:
            raise RuntimeError(
                f"REGISTRY_RELOAD_FAILED: Schema validation failed: {err}. "
                f"The previous configuration remains in effect."
            )

        # Update hash
        with self._lock:
            self._current_hash = new_hash
            self._last_verified = _now_utc_z()
            self._reload_count += 1

        # Update backup
        try:
            shutil.copy2(str(self._registry_path), str(self._backup_path))
        except OSError:
            pass

        # Log the change
        self._log_stability_event("checkpoint", {
            "description": "Registry reloaded through governed process",
            "source": "registry_reload",
            "old_hash": old_hash,
            "new_hash": new_hash,
            "tool_count": len(data.get("tools", [])),
            "changed": old_hash != new_hash,
        })

        return {
            "status": "ok",
            "old_hash": old_hash,
            "new_hash": new_hash,
            "changed": old_hash != new_hash,
            "tool_count": len(data.get("tools", [])),
            "reload_count": self._reload_count,
        }

    # -- Check (validate without reloading) ----------------------------

    def check(self) -> Dict[str, Any]:
        """Validate the current registry file without reloading.

        Returns validation results so an engineer can verify before reloading.
        """
        result = {
            "registry_path": str(self._registry_path),
            "current_active_hash": self._current_hash,
        }

        if not self._registry_path.exists():
            result["valid"] = False
            result["error"] = "File does not exist"
            return result

        try:
            raw = self._registry_path.read_bytes()
        except OSError as e:
            result["valid"] = False
            result["error"] = f"Cannot read file: {e}"
            return result

        file_hash = _sha256_bytes(raw)
        result["file_hash"] = file_hash
        result["matches_active"] = file_hash == self._current_hash

        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            result["valid"] = False
            result["error"] = f"Invalid JSON: {e}"
            return result

        valid, err = validate_registry_schema(data)
        result["valid"] = valid
        if not valid:
            result["error"] = err
        else:
            result["tool_count"] = len(data.get("tools", []))
            result["tools"] = [t.get("tool") for t in data.get("tools", [])]

        return result

    # -- Status --------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Report current registry integrity status."""
        with self._lock:
            return {
                "registry_path": str(self._registry_path),
                "startup_hash": self._startup_hash,
                "current_hash": self._current_hash,
                "last_verified": self._last_verified,
                "startup_time": self._startup_time,
                "reload_count": self._reload_count,
                "backup_path": str(self._backup_path),
                "initialized": self._startup_hash is not None,
            }

    # -- Internal helpers ----------------------------------------------

    def _log_stability_event(self, event_type: str, detail: Dict[str, Any]) -> None:
        """Log to the chain stability log."""
        try:
            # Import here to avoid circular imports at module load
            import sys
            scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from chain_health import append_stability_event
            append_stability_event(self._stability_log_path, event_type, detail)
        except Exception:
            # Stability logging is best-effort — never block governance operations
            pass


# ---------------------------------------------------------------------------
# Generic config file integrity (for messaging-tool-map and similar files)
# ---------------------------------------------------------------------------

def validate_messaging_map_schema(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate messaging-tool-map.v1.json against the expected schema."""
    if not isinstance(data, dict):
        return False, "Messaging map must be a JSON object"
    if "mapping_schema_version" not in data:
        return False, "Missing required field: mapping_schema_version"
    if "entries" not in data:
        return False, "Missing required field: entries"
    entries = data["entries"]
    if not isinstance(entries, list):
        return False, "entries must be an array"
    if len(entries) == 0:
        return False, "entries must not be empty"
    seen_ids = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return False, f"entries[{i}] must be a JSON object"
        for req in ("mapping_id", "capability_class"):
            if req not in entry:
                return False, f"entries[{i}] missing required field: {req}"
        mid = entry["mapping_id"]
        if mid in seen_ids:
            return False, f"entries[{i}] duplicate mapping_id: {mid}"
        seen_ids.add(mid)
    return True, None


class ConfigFileIntegrity:
    """Generic integrity protection for security-critical config files.

    Same model as RegistryIntegrity but with a pluggable schema validator.
    Used for messaging-tool-map.v1.json and similar configuration surfaces.
    """

    def __init__(
        self,
        config_path: Path,
        runtime_dir: Path,
        *,
        name: str = "config",
        validate_fn=None,
        backup_filename: str = "config_backup.json",
    ):
        self._config_path = config_path
        self._runtime_dir = runtime_dir
        self._name = name
        self._validate_fn = validate_fn
        self._stability_log_path = runtime_dir / "LOGS" / "chain_stability.jsonl"
        self._backup_path = runtime_dir / backup_filename
        self._lock = threading.Lock()

        self._startup_hash: Optional[str] = None
        self._current_hash: Optional[str] = None
        self._last_verified: Optional[str] = None
        self._startup_time: Optional[str] = None
        self._reload_count: int = 0

    def initialize(self, *, enforce_permissions: bool = True) -> Dict[str, Any]:
        """Initialize integrity at startup. Raises RuntimeError on fatal errors."""
        result = {"config_path": str(self._config_path), "status": "ok", "warnings": []}

        if not self._config_path.exists():
            raise RuntimeError(
                f"{self._name.upper()}_MISSING: {self._config_path} not found."
            )
        if not self._config_path.is_file():
            raise RuntimeError(
                f"{self._name.upper()}_NOT_FILE: {self._config_path} is not a regular file."
            )

        # Permission check
        try:
            mode = self._config_path.stat().st_mode & 0o777
            if mode & 0o077:
                msg = (
                    f"{self._name.upper()}_PERMISSIONS_TOO_OPEN: "
                    f"{self._config_path} has mode {oct(mode)}. Expected 0600."
                )
                if enforce_permissions:
                    result["warnings"].append(msg)
                    try:
                        os.chmod(str(self._config_path), stat.S_IRUSR | stat.S_IWUSR)
                        result["warnings"].append(
                            f"Auto-fixed permissions to 0600 on {self._config_path}"
                        )
                    except OSError as e:
                        raise RuntimeError(f"{msg} Failed to auto-fix: {e}")
                else:
                    result["warnings"].append(msg + " (enforcement disabled)")
        except OSError:
            pass

        # Read and hash
        try:
            raw = self._config_path.read_bytes()
        except OSError as e:
            raise RuntimeError(f"{self._name.upper()}_UNREADABLE: {e}")

        file_hash = _sha256_bytes(raw)

        # Parse and validate
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(f"{self._name.upper()}_INVALID_JSON: {e}")

        if self._validate_fn:
            valid, err = self._validate_fn(data)
            if not valid:
                raise RuntimeError(f"{self._name.upper()}_SCHEMA_INVALID: {err}")

        with self._lock:
            self._startup_hash = file_hash
            self._current_hash = file_hash
            self._last_verified = _now_utc_z()
            self._startup_time = _now_utc_z()

        result["hash"] = file_hash

        # Backup
        try:
            self._runtime_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(self._config_path), str(self._backup_path))
        except OSError as e:
            result["warnings"].append(f"Failed to create backup: {e}")

        self._log_stability_event("server_start", {
            "description": f"{self._name} integrity initialized",
            "config_hash": file_hash,
        })

        return result

    def verify_or_fail(self) -> str:
        """Verify file hasn't changed. Raises RuntimeError on mismatch."""
        if self._current_hash is None:
            raise RuntimeError(
                f"{self._name.upper()}_NOT_INITIALIZED: Integrity not initialized."
            )
        try:
            current = _sha256_file(self._config_path)
        except OSError as e:
            raise RuntimeError(f"{self._name.upper()}_UNREADABLE: {e}")

        with self._lock:
            self._last_verified = _now_utc_z()
            if current != self._current_hash:
                self._log_stability_event("suspicious_event", {
                    "description": f"{self._name} modified without governed reload",
                    "source": f"{self._name}_integrity",
                    "expected_hash": self._current_hash,
                    "actual_hash": current,
                })
                raise RuntimeError(
                    f"{self._name.upper()}_TAMPERED: {self._config_path} modified "
                    f"without governed reload. Expected: {self._current_hash}, "
                    f"found: {current}. Fail closed."
                )
            return current

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "config_path": str(self._config_path),
                "name": self._name,
                "startup_hash": self._startup_hash,
                "current_hash": self._current_hash,
                "last_verified": self._last_verified,
                "reload_count": self._reload_count,
                "initialized": self._startup_hash is not None,
            }

    def _log_stability_event(self, event_type: str, detail: Dict[str, Any]) -> None:
        try:
            import sys as _sys
            scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
            if str(scripts_dir) not in _sys.path:
                _sys.path.insert(0, str(scripts_dir))
            from chain_health import append_stability_event
            append_stability_event(self._stability_log_path, event_type, detail)
        except Exception:
            pass
