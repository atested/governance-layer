#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import hashlib
from pathlib import Path
from typing import Any, Optional
import json
import re

from receipt_signing import (
    verify_digest_signature_inline_pubkey,
    verify_digest_signature_with_key_input,
    write_signature_artifacts_with_key_input,
)
from inspectability_contract import (
    build_receipt_payload,
    build_recent_receipts_payload,
    build_replay_payload,
    canonical_tool_event_digests,
)
from storage_contract import receipt_index_path, receipt_run_root


HOT_FILES = frozenset(
    [
        "system/scripts/release-gate.sh",
        "system/scripts/validate-proof-bundle.sh",
    ]
)

POLICY_CONTEXT_PREFIXES: dict[str, tuple[str, ...]] = {
    "DEFAULT": ("out/",),
    "STRICT_OUT_ONLY": ("out/policy_context/allowed/",),
}

FALLBACK_CAPABILITIES: dict[str, dict[str, Any]] = {
    "FS_MOVE": {
        "tool": "FS_MOVE",
        "args": {"required": ["src_path", "dst_path"], "optional": ["overwrite"]},
    },
    "FS_COPY": {
        "tool": "FS_COPY",
        "args": {"required": ["src_path", "dst_path"], "optional": ["overwrite"]},
    },
    "FS_DELETE_EXEC": {
        "tool": "FS_DELETE_EXEC",
        "args": {"required": ["path"], "optional": []},
    },
    "FS_DELETE_NONEXEC": {
        "tool": "FS_DELETE_NONEXEC",
        "args": {"required": ["path"], "optional": []},
    },
}


def _read_registry(registry_path: Path) -> list[dict[str, Any]]:
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    tools = reg.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("CAPABILITIES_REGISTRY_INVALID")
    out = []
    for tool in tools:
        if isinstance(tool, dict):
            out.append(tool)
    return out


def capability_map(registry_path: Path) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for tool in _read_registry(registry_path):
        name = str(tool.get("tool") or tool.get("capability_class") or "")
        if name:
            merged[name] = tool
    for name, tool in FALLBACK_CAPABILITIES.items():
        if name not in merged:
            merged[name] = tool
    return merged


def _normalize_rel_path(raw: Any) -> tuple[bool, str, str]:
    if not isinstance(raw, str):
        return False, "INVALID_PARAMS", ""
    s = raw.replace("\\", "/").strip()
    if not s:
        return False, "INVALID_PARAMS", ""
    if s.startswith("/"):
        return False, "OUTSIDE_ALLOWED_ROOT", ""
    parts = []
    for seg in s.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            return False, "PATH_TRAVERSAL", ""
        parts.append(seg)
    if not parts:
        return False, "INVALID_PARAMS", ""
    return True, "NONE", "/".join(parts)


def normalize_action(registry_path: Path, action_name: str, params: Any) -> dict[str, Any]:
    cap_name = str(action_name or "").strip()
    if not cap_name:
        return {"ok": False, "reason_token": "CAPABILITY_UNKNOWN", "normalized_params": {}}
    cmap = capability_map(registry_path)
    if cap_name not in cmap:
        return {"ok": False, "reason_token": "CAPABILITY_UNKNOWN", "normalized_params": {}}
    if not isinstance(params, dict):
        return {"ok": False, "reason_token": "INVALID_PARAMS", "normalized_params": {}}

    spec = cmap[cap_name].get("args", {}) if isinstance(cmap[cap_name].get("args"), dict) else {}
    required = spec.get("required", []) if isinstance(spec.get("required"), list) else []
    optional = spec.get("optional", []) if isinstance(spec.get("optional"), list) else []
    allowed = set(required) | set(optional)
    for key in required:
        if key not in params:
            return {"ok": False, "reason_token": "INVALID_PARAMS", "normalized_params": {}}

    norm: dict[str, Any] = {}
    for key in sorted(k for k in params.keys() if k in allowed):
        value = params[key]
        if key in ("path", "src_path", "dst_path"):
            ok, token, normalized = _normalize_rel_path(value)
            if not ok:
                return {"ok": False, "reason_token": token, "normalized_params": {}}
            norm[key] = normalized
        elif key == "overwrite":
            norm[key] = bool(value)
        else:
            norm[key] = value

    if "overwrite" in allowed and "overwrite" not in norm:
        norm["overwrite"] = False

    return {"ok": True, "reason_token": "NONE", "normalized_params": norm}


def _resolve_policy_context(policy_context: Any) -> tuple[bool, str, tuple[str, ...], str]:
    raw = str(policy_context or "DEFAULT").strip().upper()
    if not raw:
        raw = "DEFAULT"
    prefixes = POLICY_CONTEXT_PREFIXES.get(raw)
    if prefixes is None:
        return False, raw, tuple(), "POLICY_CONTEXT_UNKNOWN"
    return True, raw, prefixes, "NONE"


def _is_allowed_relpath(relpath: str, allowed_prefixes: tuple[str, ...]) -> bool:
    return any(relpath.startswith(prefix) for prefix in allowed_prefixes)


def _is_hot_file(relpath: str) -> bool:
    return relpath in HOT_FILES


def admissibility_check(
    registry_path: Path,
    repo_root: Path,
    action_name: str,
    params: Any,
    policy_context: str = "DEFAULT",
) -> dict[str, Any]:
    ok_ctx, used_context, allowed_prefixes, ctx_reason = _resolve_policy_context(policy_context)
    if not ok_ctx:
        return {
            "action_name": str(action_name or ""),
            "admissible": False,
            "reason_token": ctx_reason,
            "normalized_params": {},
            "policy_context_used": used_context,
        }

    normalized = normalize_action(registry_path, action_name, params)
    if not normalized.get("ok", False):
        return {
            "action_name": action_name,
            "admissible": False,
            "reason_token": normalized.get("reason_token", "UNKNOWN"),
            "normalized_params": normalized.get("normalized_params", {}),
            "policy_context_used": used_context,
        }

    cap_name = str(action_name)
    norm = normalized["normalized_params"]
    for key in ("path", "src_path", "dst_path"):
        if key not in norm:
            continue
        relp = norm[key]
        if _is_hot_file(relp):
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "TARGET_IS_HOT_FILE",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }
        if not _is_allowed_relpath(relp, allowed_prefixes):
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "OUTSIDE_ALLOWED_ROOT",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }

    if cap_name in ("FS_MOVE", "FS_COPY"):
        src = repo_root / norm["src_path"]
        if not src.exists():
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "SRC_MISSING",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }
        dst = repo_root / norm["dst_path"]
        if dst.exists() and not bool(norm.get("overwrite", False)):
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "DEST_EXISTS",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }

    if cap_name == "FS_DELETE_EXEC":
        p = repo_root / norm["path"]
        if not p.exists():
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "SRC_MISSING",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }
        if not os.access(p, os.X_OK):
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "NOT_EXECUTABLE",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }

    if cap_name == "FS_DELETE_NONEXEC":
        p = repo_root / norm["path"]
        if not p.exists():
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "SRC_MISSING",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }
        if os.access(p, os.X_OK):
            return {
                "action_name": cap_name,
                "admissible": False,
                "reason_token": "IS_EXECUTABLE",
                "normalized_params": norm,
                "policy_context_used": used_context,
            }

    return {
        "action_name": cap_name,
        "admissible": True,
        "reason_token": "NONE",
        "normalized_params": norm,
        "policy_context_used": used_context,
    }


def execute_action(registry_path: Path, repo_root: Path, action_name: str, params: Any, dry_run: bool = False) -> dict[str, Any]:
    check = admissibility_check(registry_path, repo_root, action_name, params)
    if not check.get("admissible", False):
        return {"executed": False, **check}

    name = str(action_name)
    norm = check["normalized_params"]
    if dry_run:
        return {"executed": False, "action_name": name, "admissible": True, "reason_token": "NONE", "normalized_params": norm}

    if name == "FS_MOVE":
        src = repo_root / norm["src_path"]
        dst = repo_root / norm["dst_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if bool(norm.get("overwrite", False)) and dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.move(str(src), str(dst))
        return {"executed": True, "action_name": name, "admissible": True, "reason_token": "NONE", "normalized_params": norm}

    if name == "FS_COPY":
        src = repo_root / norm["src_path"]
        dst = repo_root / norm["dst_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return {"executed": True, "action_name": name, "admissible": True, "reason_token": "NONE", "normalized_params": norm}

    if name in ("FS_DELETE_EXEC", "FS_DELETE_NONEXEC"):
        p = repo_root / norm["path"]
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"executed": True, "action_name": name, "admissible": True, "reason_token": "NONE", "normalized_params": norm}

    return {"executed": False, "action_name": name, "admissible": False, "reason_token": "CAPABILITY_UNKNOWN", "normalized_params": {}}


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _valid_run_id(run_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", run_id))


def emit_action_record(
    repo_root: Path,
    run_id: str,
    action_name: str,
    normalized_params: dict[str, Any],
    outcome: str,
    reason_token: str,
    result: Optional[dict[str, Any]] = None,
    sign_receipt: bool = False,
    signing_key_input: str = "",
    tool_event_digests: Optional[list[str]] = None,
) -> dict[str, str]:
    if not _valid_run_id(run_id):
        raise ValueError("INVALID_RUN_ID")
    rec = {
        "action_record_version": "v0",
        "action_name": action_name,
        "normalized_params": normalized_params,
        "outcome": outcome,
        "reason_token": reason_token,
        "result": result or {},
    }
    cleaned_tool_event_digests: list[str] = []
    if isinstance(tool_event_digests, list):
        for item in tool_event_digests:
            token = str(item or "").strip()
            if re.fullmatch(r"sha256:[0-9a-f]{64}", token):
                cleaned_tool_event_digests.append(token)
    cleaned_tool_event_digests = sorted(set(cleaned_tool_event_digests))
    if cleaned_tool_event_digests:
        rec["tool_event_digests"] = cleaned_tool_event_digests
    body = _canonical_json(rec) + "\n"
    digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    out_dir = receipt_run_root(repo_root, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "action_record.json").write_text(body, encoding="utf-8")
    (out_dir / "action_record.sha256").write_text(digest + "\n", encoding="utf-8")
    signature_present = False
    signature_valid = False
    if sign_receipt:
        signing_key = signing_key_input.strip()
        if not signing_key:
            raise ValueError("SIGNING_KEY_MISSING")
        signed = write_signature_artifacts_with_key_input(out_dir, digest, signing_key)
        signature_present = True
        signature_valid = verify_digest_signature_inline_pubkey(
            digest, signed["signature"], signed["public_key_pem"]
        )
    _update_receipt_index(repo_root, run_id, digest, action_name, outcome)
    return {
        "digest": digest,
        "signature_present": "true" if signature_present else "false",
        "signature_valid": "true" if signature_valid else "false",
    }


def _update_receipt_index(repo_root: Path, run_id: str, digest: str, action_name: str, outcome: str) -> None:
    index_path = receipt_index_path(repo_root)
    out_root = index_path.parent
    out_root.mkdir(parents=True, exist_ok=True)
    entries = []
    if index_path.exists():
        try:
            obj = json.loads(index_path.read_text(encoding="utf-8"))
            loaded = obj.get("receipts", [])
            if isinstance(loaded, list):
                for rec in loaded:
                    if isinstance(rec, dict):
                        entries.append(
                            {
                                "run_id": str(rec.get("run_id", "")),
                                "digest": str(rec.get("digest", "")),
                                "action_name": str(rec.get("action_name", "")),
                                "outcome": str(rec.get("outcome", "")),
                            }
                        )
        except Exception:
            entries = []

    entries = [r for r in entries if r.get("run_id") != run_id]
    entries.append(
        {
            "run_id": run_id,
            "digest": digest,
            "action_name": action_name,
            "outcome": outcome,
        }
    )
    entries.sort(key=lambda r: r["run_id"])
    payload = {"receipt_index_version": "v1", "receipts": entries}
    index_path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")


def _index_rows(repo_root: Path) -> list[dict[str, str]]:
    index_path = receipt_index_path(repo_root)
    if not index_path.exists():
        return []
    try:
        obj = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = obj.get("receipts", [])
    if not isinstance(rows, list):
        return []
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned.append(
            {
                "run_id": str(row.get("run_id", "")),
                "digest": str(row.get("digest", "")),
                "action_name": str(row.get("action_name", "")),
                "outcome": str(row.get("outcome", "")),
            }
        )
    cleaned.sort(key=lambda r: r["run_id"])
    return cleaned


def load_receipt(
    repo_root: Path, run_id: str, verify_signature: bool = False, pubkey: str = ""
) -> dict[str, Any]:
    rows = _index_rows(repo_root)
    row = next((r for r in rows if r["run_id"] == run_id), None)
    if row is None:
        raise ValueError("RECEIPT_NOT_FOUND")
    rec_path = receipt_run_root(repo_root, run_id) / "action_record.json"
    if not rec_path.exists():
        raise ValueError("RECEIPT_NOT_FOUND")
    body = rec_path.read_text(encoding="utf-8")
    record = json.loads(body)
    computed = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    sig_path = receipt_run_root(repo_root, run_id) / "action_record.sig"
    sigmeta_path = receipt_run_root(repo_root, run_id) / "action_record.sigmeta.json"
    signature_present = sig_path.exists() and sigmeta_path.exists()
    signature_valid = False
    signature_reason = "NONE"
    tool_event_digests = canonical_tool_event_digests(record.get("tool_event_digests", []))
    if verify_signature:
        if not signature_present:
            signature_reason = "SIGNATURE_MISSING"
        elif not pubkey.strip():
            signature_reason = "PUBKEY_MISSING"
        else:
            try:
                sig = sig_path.read_text(encoding="utf-8").strip()
                sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
                meta_digest = str(sigmeta.get("digest", ""))
                if meta_digest != row["digest"]:
                    signature_reason = "SIGNATURE_INVALID"
                elif verify_digest_signature_with_key_input(row["digest"], sig, pubkey):
                    signature_valid = True
                    signature_reason = "NONE"
                else:
                    signature_reason = "SIGNATURE_INVALID"
            except Exception:
                signature_reason = "SIGNATURE_INVALID"
    return build_receipt_payload(
        repo_root=repo_root,
        run_id=run_id,
        digest=row["digest"],
        action_record=record,
        digest_valid=row["digest"] == computed,
        signature_present=signature_present,
        signature_valid=signature_valid,
        signature_reason_token=signature_reason,
    )


def list_recent_receipts(repo_root: Path, limit: int) -> dict[str, Any]:
    n = max(1, min(int(limit), 50))
    rows = _index_rows(repo_root)
    selected = rows[-n:]
    linked_counts: dict[str, int] = {}
    for row in selected:
        run_id = str(row.get("run_id", ""))
        rec_path = receipt_run_root(repo_root, run_id) / "action_record.json"
        if not rec_path.is_file():
            linked_counts[run_id] = 0
            continue
        try:
            record = json.loads(rec_path.read_text(encoding="utf-8"))
        except Exception:
            linked_counts[run_id] = 0
            continue
        linked_counts[run_id] = len(canonical_tool_event_digests(record.get("tool_event_digests", [])))
    return build_recent_receipts_payload(repo_root, selected, linked_counts)


def replay_check(
    registry_path: Path,
    repo_root: Path,
    run_id: str,
    verify_signature: bool = False,
    pubkey: str = "",
    policy_context: str = "DEFAULT",
    emit_artifact: bool = False,
) -> dict[str, Any]:
    receipt = load_receipt(repo_root, run_id, verify_signature=verify_signature, pubkey=pubkey)
    ok_ctx, used_context, _allowed_prefixes, ctx_reason = _resolve_policy_context(policy_context)
    if not ok_ctx:
        return {
            "replay_version": "v0",
            "run_id": run_id,
            "digest": receipt.get("digest", ""),
            "digest_valid": bool(receipt.get("digest_valid", False)),
            "admissible_now": False,
            "reason_token": ctx_reason,
            "action_name": "",
            "normalized_params": {},
            "signature_present": bool(receipt.get("signature_present", False)),
            "signature_valid": bool(receipt.get("signature_valid", False)),
            "signature_reason_token": str(receipt.get("signature_reason_token", "NONE")),
            "policy_context_used": used_context,
        }
    if not receipt.get("digest_valid", False):
        return {
            "replay_version": "v0",
            "run_id": run_id,
            "digest": receipt.get("digest", ""),
            "digest_valid": False,
            "admissible_now": False,
            "reason_token": "DIGEST_MISMATCH",
            "action_name": "",
            "normalized_params": {},
            "signature_present": bool(receipt.get("signature_present", False)),
            "signature_valid": bool(receipt.get("signature_valid", False)),
            "signature_reason_token": str(receipt.get("signature_reason_token", "NONE")),
            "policy_context_used": used_context,
        }
    if verify_signature and not bool(receipt.get("signature_valid", False)):
        return {
            "replay_version": "v0",
            "run_id": run_id,
            "digest": receipt.get("digest", ""),
            "digest_valid": True,
            "admissible_now": False,
            "reason_token": str(receipt.get("signature_reason_token", "SIGNATURE_INVALID")),
            "action_name": "",
            "normalized_params": {},
            "signature_present": bool(receipt.get("signature_present", False)),
            "signature_valid": bool(receipt.get("signature_valid", False)),
            "signature_reason_token": str(receipt.get("signature_reason_token", "NONE")),
            "policy_context_used": used_context,
        }

    record = receipt.get("action_record", {})
    action_name = str(record.get("action_name", ""))
    norm_params = record.get("normalized_params", {})
    check = admissibility_check(
        registry_path, repo_root, action_name, norm_params, policy_context=used_context
    )
    response = build_replay_payload(
        repo_root=repo_root,
        run_id=run_id,
        digest=str(receipt.get("digest", "")),
        digest_valid=True,
        admissible_now=bool(check.get("admissible", False)),
        reason_token=str(check.get("reason_token", "UNKNOWN")),
        action_name=action_name,
        normalized_params=check.get("normalized_params", {}),
        signature_present=bool(receipt.get("signature_present", False)),
        signature_valid=bool(receipt.get("signature_valid", False)),
        signature_reason_token=str(receipt.get("signature_reason_token", "NONE")),
        tool_event_digests=receipt.get("tool_event_digests", []),
        policy_context_used=str(check.get("policy_context_used", used_context)),
    )
    if emit_artifact:
        artifact = {
            "replay_check_version": "v0",
            "run_id": run_id,
            "receipt_digest": str(receipt.get("digest", "")),
            "policy_context_used": str(response.get("policy_context_used", used_context)),
            "digest_valid": bool(response.get("digest_valid", False)),
            "admissible_now": bool(response.get("admissible_now", False)),
            "reason_token": str(response.get("reason_token", "UNKNOWN")),
        }
        digest_list = receipt.get("tool_event_digests", [])
        if isinstance(digest_list, list):
            vals: list[str] = []
            for item in digest_list:
                token = str(item or "").strip()
                if re.fullmatch(r"sha256:[0-9a-f]{64}", token):
                    vals.append(token)
            vals = sorted(set(vals))
            if vals:
                artifact["tool_event_digests"] = vals
        out_dir = receipt_run_root(repo_root, run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "replay_check.v0.json").write_text(
            _canonical_json(artifact) + "\n",
            encoding="utf-8",
        )
    return response
