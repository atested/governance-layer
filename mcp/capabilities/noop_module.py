from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from capabilities.base import CapabilityDescribe, CapabilityModule


class NoopEchoCapabilityModule(CapabilityModule):
    name = "NOOP_ECHO"

    def describe(self) -> CapabilityDescribe:
        return CapabilityDescribe(
            name=self.name,
            params=[{"name": "echo", "required": False, "type": "string"}],
            reason_tokens=["NONE"],
        )

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            return {"ok": False, "reason_token": "INVALID_PARAMS", "normalized_params": {}}
        echo = params.get("echo", "")
        if not isinstance(echo, str):
            return {"ok": False, "reason_token": "INVALID_PARAMS", "normalized_params": {}}
        return {"ok": True, "reason_token": "NONE", "normalized_params": {"echo": echo.strip()}}

    def admissibility_check(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        policy_context: str = "DEFAULT",
    ) -> Dict[str, Any]:
        norm = self.normalize_action(registry_path, params)
        used = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
        if not norm.get("ok", False):
            return {
                "action_name": self.name,
                "admissible": False,
                "reason_token": str(norm.get("reason_token", "INVALID_PARAMS")),
                "normalized_params": norm.get("normalized_params", {}),
                "policy_context_used": used,
            }
        return {
            "action_name": self.name,
            "admissible": True,
            "reason_token": "NONE",
            "normalized_params": norm.get("normalized_params", {}),
            "policy_context_used": used,
        }

    def execute(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        dry_run: bool = False,
        run_id: str = "default",
    ) -> Dict[str, Any]:
        check = self.admissibility_check(registry_path, repo_root, params, policy_context="DEFAULT")
        if not check.get("admissible", False):
            return {"executed": False, **check}
        if dry_run:
            return {
                "executed": False,
                "action_name": self.name,
                "admissible": True,
                "reason_token": "NONE",
                "normalized_params": check.get("normalized_params", {}),
            }
        return {
            "executed": True,
            "action_name": self.name,
            "admissible": True,
            "reason_token": "NONE",
            "normalized_params": check.get("normalized_params", {}),
        }
