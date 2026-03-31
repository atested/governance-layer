from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from capabilities.base import CapabilityDescribe, CapabilityModule
from tool_catalog_store import get as store_get
from tool_catalog_store import list_recent as store_list_recent
from tool_catalog_store import list_slice as store_list_slice
from tool_catalog_store import normalize_tool_doc, put as store_put
from tool_catalog_store import summarize_slice as store_summarize_slice


class ToolCatalogCapabilityModule(CapabilityModule):
    name = "TOOL_REGISTER"

    def describe(self) -> CapabilityDescribe:
        return CapabilityDescribe(
            name=self.name,
            params=[
                {"name": "tool_name", "required": True, "type": "string"},
                {"name": "tool_version", "required": True, "type": "string"},
                {"name": "schema_json", "required": True, "type": "object"},
                {"name": "declared_capabilities", "required": True, "type": "array"},
                {"name": "created_from", "required": False, "type": "string"},
            ],
            reason_tokens=[
                "OK",
                "TOOL_DOC_INVALID",
                "TOOL_DOC_TOO_LARGE",
            ],
        )

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            return {"ok": False, "reason_token": "TOOL_DOC_INVALID", "normalized_params": {}}
        try:
            doc = normalize_tool_doc(params)
        except ValueError as exc:
            return {"ok": False, "reason_token": str(exc), "normalized_params": {}}
        return {"ok": True, "reason_token": "OK", "normalized_params": doc}

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
                "reason_token": str(norm.get("reason_token", "TOOL_DOC_INVALID")),
                "normalized_params": {},
                "policy_context_used": used,
            }
        return {
            "action_name": self.name,
            "admissible": True,
            "reason_token": "OK",
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
        check = self.admissibility_check(registry_path, repo_root, params)
        if not check.get("admissible", False):
            return {"executed": False, **check}
        normalized = dict(check.get("normalized_params", {}))
        if dry_run:
            return {
                "executed": False,
                "action_name": self.name,
                "admissible": True,
                "reason_token": "OK",
                "normalized_params": normalized,
            }
        tool_id = store_put(repo_root, normalized)
        return {
            "executed": True,
            "action_name": self.name,
            "admissible": True,
            "reason_token": "OK",
            "normalized_params": normalized,
            "result": {
                "tool_id": tool_id,
                "schema_sha256": str(normalized.get("schema_sha256", "")),
            },
        }

    def query_get(self, repo_root: Path, tool_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
        doc = store_get(repo_root, tool_id)
        used = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
        if doc is None:
            return {
                "ok": False,
                "reason_token": "TOOL_NOT_FOUND",
                "tool_doc": None,
                "policy_context_used": used,
                "POLICY_BYPASS": "READ_ONLY_QUERY",
            }
        return {
            "ok": True,
            "reason_token": "OK",
            "tool_doc": doc,
            "policy_context_used": used,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    def query_list_recent(self, repo_root: Path, limit: int, policy_context: str = "DEFAULT") -> Dict[str, Any]:
        used = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
        return {
            "ok": True,
            "reason_token": "OK",
            "tools": store_list_recent(repo_root, limit),
            "policy_context_used": used,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    def query_list_slice(
        self,
        repo_root: Path,
        created_from: str = "any",
        capability: str = "",
        limit: int = 25,
        policy_context: str = "DEFAULT",
    ) -> Dict[str, Any]:
        used = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
        try:
            tools = store_list_slice(
                repo_root,
                created_from=created_from,
                capability=capability,
                limit=limit,
            )
        except ValueError as exc:
            return {
                "ok": False,
                "reason_token": str(exc),
                "tool_catalog_slice_version": "tool_catalog_slice_v1",
                "filters": {
                    "created_from": str(created_from or "any").strip().lower() or "any",
                    "capability": str(capability or "").strip().upper(),
                    "limit": str(limit),
                },
                "selected_count": 0,
                "tools": [],
                "policy_context_used": used,
                "POLICY_BYPASS": "READ_ONLY_QUERY",
            }
        return {
            "ok": True,
            "reason_token": "OK",
            "tool_catalog_slice_version": "tool_catalog_slice_v1",
            "filters": {
                "created_from": str(created_from or "any").strip().lower() or "any",
                "capability": str(capability or "").strip().upper(),
                "limit": max(1, min(int(limit), 500)),
            },
            "selected_count": len(tools),
            "tools": tools,
            "policy_context_used": used,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    def query_summarize_slice(
        self,
        repo_root: Path,
        created_from: str = "any",
        capability: str = "",
        limit: int = 25,
        policy_context: str = "DEFAULT",
    ) -> Dict[str, Any]:
        used = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
        try:
            summary = store_summarize_slice(
                repo_root,
                created_from=created_from,
                capability=capability,
                limit=limit,
            )
        except ValueError as exc:
            return {
                "ok": False,
                "reason_token": str(exc),
                "summary_version": "tool_catalog_slice_summary_v1",
                "filters": {
                    "created_from": str(created_from or "any").strip().lower() or "any",
                    "capability": str(capability or "").strip().upper(),
                    "limit": str(limit),
                },
                "selected_count": 0,
                "selected_tool_ids": [],
                "counts": {
                    "by_created_from": {},
                    "by_declared_capability": {},
                },
                "items": [],
                "policy_context_used": used,
                "POLICY_BYPASS": "READ_ONLY_QUERY",
            }
        return {
            "ok": True,
            "reason_token": "OK",
            **summary,
            "policy_context_used": used,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }
