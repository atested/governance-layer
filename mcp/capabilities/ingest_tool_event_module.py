from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict

from capabilities.base import CapabilityDescribe, CapabilityModule
from tool_event_store import upsert_tool_event_index

MAX_EVENT_BYTES = 16384
MAX_OUTPUTS = 64
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class IngestToolEventCapabilityModule(CapabilityModule):
    name = "INGEST_TOOL_EVENT"

    def describe(self) -> CapabilityDescribe:
        return CapabilityDescribe(
            name=self.name,
            params=[
                {"name": "tool_event_version", "required": True, "type": "string"},
                {"name": "tool_name", "required": True, "type": "string"},
                {"name": "tool_params_digest", "required": True, "type": "string"},
                {"name": "exit_code", "required": True, "type": "int"},
                {"name": "outputs", "required": True, "type": "array"},
                {"name": "policy_context_used", "required": True, "type": "string"},
                {"name": "provenance", "required": True, "type": "object"},
            ],
            reason_tokens=[
                "OK",
                "PROVENANCE_MISSING",
                "TOOL_EVENT_DIGEST_INVALID",
                "TOOL_EVENT_MISSING_FIELD",
                "TOOL_EVENT_SCHEMA_INVALID",
                "TOOL_EVENT_TOO_LARGE",
            ],
        )

    def _normalize_provenance(self, value: Any) -> tuple[bool, str, dict[str, str]]:
        if not isinstance(value, dict):
            return False, "PROVENANCE_MISSING", {}
        source = value.get("source_identifier")
        extraction = value.get("extraction_date")
        if not isinstance(source, str) or not source.strip():
            return False, "PROVENANCE_MISSING", {}
        if not isinstance(extraction, str) or not extraction.strip():
            return False, "PROVENANCE_MISSING", {}
        return (
            True,
            "OK",
            {
                "source_identifier": source.strip(),
                "extraction_date": extraction.strip(),
            },
        )

    def _normalize_outputs(self, outputs: Any) -> tuple[bool, str, list[dict[str, str]]]:
        if not isinstance(outputs, list):
            return False, "TOOL_EVENT_SCHEMA_INVALID", []
        if len(outputs) > MAX_OUTPUTS:
            return False, "TOOL_EVENT_TOO_LARGE", []
        normalized: list[dict[str, str]] = []
        for item in outputs:
            if not isinstance(item, dict):
                return False, "TOOL_EVENT_SCHEMA_INVALID", []
            name = item.get("name")
            digest = item.get("digest")
            ref_type = item.get("ref_type")
            if not isinstance(name, str) or not name.strip():
                return False, "TOOL_EVENT_MISSING_FIELD", []
            if not isinstance(ref_type, str) or not ref_type.strip():
                return False, "TOOL_EVENT_MISSING_FIELD", []
            if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
                return False, "TOOL_EVENT_DIGEST_INVALID", []
            normalized.append(
                {
                    "digest": digest,
                    "name": name.strip(),
                    "ref_type": ref_type.strip(),
                }
            )
        normalized.sort(key=lambda x: (x["name"], x["digest"], x["ref_type"]))
        return True, "OK", normalized

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            return {"ok": False, "reason_token": "TOOL_EVENT_SCHEMA_INVALID", "normalized_params": {}}

        required = [
            "tool_event_version",
            "tool_name",
            "tool_params_digest",
            "exit_code",
            "outputs",
            "policy_context_used",
            "provenance",
        ]
        for key in required:
            if key not in params:
                return {"ok": False, "reason_token": "TOOL_EVENT_MISSING_FIELD", "normalized_params": {}}

        version = params.get("tool_event_version")
        tool_name = params.get("tool_name")
        tool_params_digest = params.get("tool_params_digest")
        exit_code = params.get("exit_code")
        policy_context_used = params.get("policy_context_used")
        if not isinstance(version, str) or version.strip() != "v0":
            return {"ok": False, "reason_token": "TOOL_EVENT_SCHEMA_INVALID", "normalized_params": {}}
        if not isinstance(tool_name, str) or not _TOOL_NAME_RE.fullmatch(tool_name.strip()):
            return {"ok": False, "reason_token": "TOOL_EVENT_SCHEMA_INVALID", "normalized_params": {}}
        if not isinstance(tool_params_digest, str) or not _DIGEST_RE.fullmatch(tool_params_digest.strip()):
            return {"ok": False, "reason_token": "TOOL_EVENT_DIGEST_INVALID", "normalized_params": {}}
        if not isinstance(exit_code, int):
            return {"ok": False, "reason_token": "TOOL_EVENT_SCHEMA_INVALID", "normalized_params": {}}
        if not isinstance(policy_context_used, str) or not policy_context_used.strip():
            return {"ok": False, "reason_token": "TOOL_EVENT_MISSING_FIELD", "normalized_params": {}}

        ok_out, out_reason, outputs = self._normalize_outputs(params.get("outputs"))
        if not ok_out:
            return {"ok": False, "reason_token": out_reason, "normalized_params": {}}

        ok_prov, prov_reason, provenance = self._normalize_provenance(params.get("provenance"))
        if not ok_prov:
            return {"ok": False, "reason_token": prov_reason, "normalized_params": {}}

        normalized = {
            "exit_code": exit_code,
            "outputs": outputs,
            "policy_context_used": policy_context_used.strip(),
            "provenance": provenance,
            "tool_event_version": "v0",
            "tool_name": tool_name.strip(),
            "tool_params_digest": tool_params_digest.strip(),
        }
        body = json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n"
        if len(body.encode("utf-8")) > MAX_EVENT_BYTES:
            return {"ok": False, "reason_token": "TOOL_EVENT_TOO_LARGE", "normalized_params": {}}
        return {"ok": True, "reason_token": "OK", "normalized_params": normalized}

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
                "reason_token": str(norm.get("reason_token", "TOOL_EVENT_SCHEMA_INVALID")),
                "normalized_params": norm.get("normalized_params", {}),
                "policy_context_used": used,
            }
        normalized = dict(norm.get("normalized_params", {}))
        normalized["policy_context_used"] = used
        return {
            "action_name": self.name,
            "admissible": True,
            "reason_token": "OK",
            "normalized_params": normalized,
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

        normalized = dict(check.get("normalized_params", {}))
        if dry_run:
            return {
                "executed": False,
                "action_name": self.name,
                "admissible": True,
                "reason_token": "OK",
                "normalized_params": normalized,
            }

        if not _RUN_ID_RE.fullmatch(run_id):
            return {
                "executed": False,
                "action_name": self.name,
                "admissible": False,
                "reason_token": "TOOL_EVENT_SCHEMA_INVALID",
                "normalized_params": normalized,
            }

        out_rel_dir = f"out/mcp_ingest_tool_event/{run_id}"
        out_dir = repo_root / out_rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        event_rel = f"{out_rel_dir}/tool_event.v0.json"
        event_path = repo_root / event_rel
        event_body = json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n"
        event_path.write_text(event_body, encoding="utf-8")
        event_sha = "sha256:" + hashlib.sha256(event_body.encode("utf-8")).hexdigest()

        ingest_record = {
            "action_record_version": "v0",
            "action_name": self.name,
            "normalized_params": normalized,
            "outcome": "EXECUTED",
            "reason_token": "OK",
            "result": {
                "tool_event_ref": event_rel,
                "tool_event_sha256": event_sha,
            },
        }
        record_body = json.dumps(ingest_record, sort_keys=True, separators=(",", ":")) + "\n"
        record_rel = f"{out_rel_dir}/action_record.json"
        record_path = repo_root / record_rel
        record_path.write_text(record_body, encoding="utf-8")
        record_digest = "sha256:" + hashlib.sha256(record_body.encode("utf-8")).hexdigest()
        (out_dir / "action_record.sha256").write_text(record_digest + "\n", encoding="utf-8")
        store_info = upsert_tool_event_index(
            repo_root=repo_root,
            run_id=run_id,
            tool_event_digest=event_sha,
            tool_event_ref=event_rel,
            action_record_ref=record_rel,
        )

        return {
            "executed": True,
            "action_name": self.name,
            "admissible": True,
            "reason_token": "OK",
            "normalized_params": normalized,
            "ingest_result": {
                "tool_event_ref": event_rel,
                "tool_event_sha256": event_sha,
                "action_record_ref": record_rel,
                "action_record_digest": record_digest,
                "stored_seq": int(store_info.get("stored_seq", 0)),
                "TOOL_EVENT_STORE_COLLISION": str(store_info.get("TOOL_EVENT_STORE_COLLISION", "NO")),
            },
        }
