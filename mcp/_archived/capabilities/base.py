from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class CapabilityDescribe:
    name: str
    params: list[Dict[str, Any]]
    reason_tokens: list[str]


class CapabilityModule:
    name: str

    def describe(self) -> CapabilityDescribe:
        raise NotImplementedError

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def admissibility_check(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        policy_context: str = "DEFAULT",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def execute(
        self,
        registry_path: Path,
        repo_root: Path,
        params: Dict[str, Any],
        dry_run: bool = False,
        run_id: str = "default",
    ) -> Dict[str, Any]:
        raise NotImplementedError
