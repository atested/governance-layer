from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from capability_introspection import admissibility_check, execute_action, normalize_action
from capabilities.base import CapabilityDescribe, CapabilityModule


_CAP_REASON_TOKENS: dict[str, list[str]] = {
    "FS_MOVE": ["DEST_EXISTS", "OUTSIDE_ALLOWED_ROOT", "PATH_TRAVERSAL", "SRC_MISSING", "TARGET_IS_HOT_FILE"],
    "FS_COPY": ["DEST_EXISTS", "OUTSIDE_ALLOWED_ROOT", "PATH_TRAVERSAL", "SRC_MISSING", "TARGET_IS_HOT_FILE"],
    "FS_DELETE_EXEC": ["NOT_EXECUTABLE", "OUTSIDE_ALLOWED_ROOT", "PATH_TRAVERSAL", "SRC_MISSING", "TARGET_IS_HOT_FILE"],
    "FS_DELETE_NONEXEC": ["IS_EXECUTABLE", "OUTSIDE_ALLOWED_ROOT", "PATH_TRAVERSAL", "SRC_MISSING", "TARGET_IS_HOT_FILE"],
}


class FilesystemCapabilityModule(CapabilityModule):
    def __init__(self, name: str, args_spec: Dict[str, Any]) -> None:
        self.name = name
        self._args_spec = args_spec if isinstance(args_spec, dict) else {}

    def describe(self) -> CapabilityDescribe:
        required = self._args_spec.get("required", []) if isinstance(self._args_spec.get("required"), list) else []
        optional = self._args_spec.get("optional", []) if isinstance(self._args_spec.get("optional"), list) else []
        params = []
        for pname in sorted(set(str(x) for x in required)):
            params.append({"name": pname, "required": True, "type": "path" if "path" in pname else "string"})
        for pname in sorted(set(str(x) for x in optional)):
            if pname in required:
                continue
            ptype = "bool" if pname == "overwrite" else ("path" if "path" in pname else "string")
            params.append({"name": pname, "required": False, "type": ptype})
        return CapabilityDescribe(name=self.name, params=params, reason_tokens=sorted(_CAP_REASON_TOKENS.get(self.name, [])))

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_action(registry_path, self.name, params)

    def admissibility_check(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        policy_context: str = "DEFAULT",
    ) -> Dict[str, Any]:
        return admissibility_check(registry_path, repo_root, self.name, params, policy_context=policy_context)

    def execute(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        dry_run: bool = False,
        run_id: str = "default",
    ) -> Dict[str, Any]:
        return execute_action(registry_path, repo_root, self.name, params, dry_run=dry_run)
