from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict

from capabilities.base import CapabilityDescribe, CapabilityModule

MAX_ARTIFACT_BYTES = 4096
_RUN_ID_RE = re.compile(r"[A-Za-z0-9._-]+$")


class IngestArtifactCapabilityModule(CapabilityModule):
    name = "INGEST_ARTIFACT"

    def describe(self) -> CapabilityDescribe:
        return CapabilityDescribe(
            name=self.name,
            params=[
                {"name": "artifact_path", "required": False, "type": "path"},
                {"name": "payload_b64", "required": False, "type": "string"},
                {"name": "provenance", "required": True, "type": "object"},
            ],
            reason_tokens=[
                "ARTIFACT_MISSING",
                "ARTIFACT_NOT_UNDER_OUT",
                "ARTIFACT_PATH_INVALID",
                "ARTIFACT_TOO_LARGE",
                "OK",
                "PROVENANCE_MISSING",
            ],
        )

    def _normalize_rel_out_path(self, value: Any) -> tuple[bool, str, str]:
        if not isinstance(value, str):
            return False, "ARTIFACT_PATH_INVALID", ""
        path = value.replace("\\", "/").strip()
        if not path:
            return False, "ARTIFACT_PATH_INVALID", ""
        if path.startswith("/") or path.startswith("../") or "/../" in path:
            return False, "ARTIFACT_PATH_INVALID", ""
        parts = []
        for seg in path.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                return False, "ARTIFACT_PATH_INVALID", ""
            parts.append(seg)
        if not parts:
            return False, "ARTIFACT_PATH_INVALID", ""
        normalized = "/".join(parts)
        if not normalized.startswith("out/"):
            return False, "ARTIFACT_NOT_UNDER_OUT", ""
        return True, "OK", normalized

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

    def _decode_inline_payload(self, payload_b64: str) -> tuple[bool, str, bytes]:
        try:
            blob = base64.b64decode(payload_b64.encode("ascii"), validate=True)
        except Exception:
            return False, "ARTIFACT_PATH_INVALID", b""
        if len(blob) > MAX_ARTIFACT_BYTES:
            return False, "ARTIFACT_TOO_LARGE", b""
        return True, "OK", blob

    def normalize_action(self, registry_path: Path, params: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(params, dict):
            return {"ok": False, "reason_token": "ARTIFACT_MISSING", "normalized_params": {}}

        ok_prov, prov_reason, provenance = self._normalize_provenance(params.get("provenance"))
        if not ok_prov:
            return {"ok": False, "reason_token": prov_reason, "normalized_params": {}}

        has_inline = isinstance(params.get("payload_b64"), str) and bool(str(params.get("payload_b64")).strip())
        has_path = "artifact_path" in params and params.get("artifact_path") is not None
        if not has_inline and not has_path:
            return {"ok": False, "reason_token": "ARTIFACT_MISSING", "normalized_params": {}}

        normalized: Dict[str, Any] = {"provenance": provenance}
        if has_inline:
            payload_b64 = str(params.get("payload_b64")).strip()
            ok, reason, _ = self._decode_inline_payload(payload_b64)
            if not ok:
                return {"ok": False, "reason_token": reason, "normalized_params": {}}
            normalized["source"] = "inline"
            normalized["payload_b64"] = payload_b64
            return {"ok": True, "reason_token": "OK", "normalized_params": normalized}

        ok_path, path_reason, relpath = self._normalize_rel_out_path(params.get("artifact_path"))
        if not ok_path:
            return {"ok": False, "reason_token": path_reason, "normalized_params": {}}
        normalized["source"] = "path"
        normalized["artifact_path"] = relpath
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
                "reason_token": str(norm.get("reason_token", "ARTIFACT_MISSING")),
                "normalized_params": norm.get("normalized_params", {}),
                "policy_context_used": used,
            }

        normalized = dict(norm.get("normalized_params", {}))
        if normalized.get("source") == "path":
            relpath = str(normalized.get("artifact_path", ""))
            src = repo_root / relpath
            if not src.is_file():
                return {
                    "action_name": self.name,
                    "admissible": False,
                    "reason_token": "ARTIFACT_MISSING",
                    "normalized_params": normalized,
                    "policy_context_used": used,
                }
            if src.stat().st_size > MAX_ARTIFACT_BYTES:
                return {
                    "action_name": self.name,
                    "admissible": False,
                    "reason_token": "ARTIFACT_TOO_LARGE",
                    "normalized_params": normalized,
                    "policy_context_used": used,
                }

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
                "reason_token": "ARTIFACT_PATH_INVALID",
                "normalized_params": normalized,
            }

        if normalized.get("source") == "inline":
            _, _, blob = self._decode_inline_payload(str(normalized.get("payload_b64", "")))
            if len(blob) > MAX_ARTIFACT_BYTES:
                return {
                    "executed": False,
                    "action_name": self.name,
                    "admissible": False,
                    "reason_token": "ARTIFACT_TOO_LARGE",
                    "normalized_params": normalized,
                }
        else:
            src = repo_root / str(normalized.get("artifact_path", ""))
            blob = src.read_bytes()

        out_rel_dir = f"out/mcp_ingest/{run_id}"
        out_dir = repo_root / out_rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        artifact_rel = f"{out_rel_dir}/artifact.bin"
        artifact_path = repo_root / artifact_rel
        artifact_path.write_bytes(blob)
        artifact_sha = "sha256:" + hashlib.sha256(blob).hexdigest()

        ingest_record = {
            "action_record_version": "v0",
            "action_name": self.name,
            "normalized_params": normalized,
            "outcome": "EXECUTED",
            "reason_token": "OK",
            "result": {
                "artifact_ref": artifact_rel,
                "bytes": len(blob),
                "artifact_sha256": artifact_sha,
            },
        }
        body = json.dumps(ingest_record, sort_keys=True, separators=(",", ":")) + "\n"
        record_rel = f"{out_rel_dir}/action_record.json"
        record_path = repo_root / record_rel
        record_path.write_text(body, encoding="utf-8")
        record_digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
        (out_dir / "action_record.sha256").write_text(record_digest + "\n", encoding="utf-8")

        return {
            "executed": True,
            "action_name": self.name,
            "admissible": True,
            "reason_token": "OK",
            "normalized_params": normalized,
            "ingest_result": {
                "artifact_ref": artifact_rel,
                "artifact_sha256": artifact_sha,
                "action_record_ref": record_rel,
                "action_record_digest": record_digest,
            },
        }
